# Genesis ML Evaluation v0.1 — Dataset & Training Pipeline Audit

**Scope:** audit of the existing failure-risk and diagnosis learning path, followed by the narrowly scoped horizon-eligibility correction recorded below. No model was trained, no feature contract or estimator behavior was changed, and no predictive-performance claim is made.

## 1. Executive summary

Genesis builds synthetic telemetry trajectories, labels records by whether a failure event occurs in the next ten observations, constructs the ordered deployable feature set, and trains Random Forest pipelines in memory. The failure-risk model uses 38 explicit features. Training and test records are grouped by `robot_id`, so a robot's rows do not cross the normal risk split. The preprocessor is fit inside the training pipeline.

The audit identified a **label validity problem**, now corrected: incomplete future horizons receive `label=None` and `failure_type_label=None` while remaining in the dataset. Normal risk, validation risk, and diagnosis training now share one eligibility selector requiring a valid horizon and known binary risk target. On the main 10,000-row generator, 9,000 rows are eligible and 1,000 are retained but unknown. The earlier “48 eligible / 952 incomplete” interpretation was incorrect; those were the old positive/negative label counts among 1,000 incomplete rows.

There is no literal simulator-only field in the 38-feature allowlist. There is, however, strong **simulator-specific proxy coupling**: thermal features measure the same temperature trajectory used by the thermal failure condition; battery level is itself one conjunct of the battery failure condition, and the other battery telemetry channels are generated from hidden simulated battery health/stress. This is a meaningful shortcut-learning risk, not direct same-row label leakage.

The available CSVs provide a 100-robot, 10,000-observation synthetic training population. Current feature engineering reproduces every saved allowlisted feature cell checked. The available runtime has no `scikit-learn`, and no fitted model artifact exists, so this audit reports no new fitted-model metrics.

## 2. Current data pipeline

The normal `main.py` path is (`main.py` `build_feature_dataset()` / `main()`, `dataset_generator.py` `DatasetGenerator.generate()`):

1. `main.py` seeds Python's global random generator with 42 and sets `GENERATE_NEW_DATASET=True`.
2. `build_feature_dataset()` constructs `DatasetGenerator(number_of_robots=100, time_steps=100)`. Its default output is `data/raw_dataset_v2.csv`; it makes 100 robot trajectories, 100 observations each.
3. `FleetSimulator` creates identities, operating conditions, hidden state, synthetic telemetry, and `failure_event` / `failure_type` ground truth.
4. `LabelGenerator(prediction_window=10)` labels each record from later records on the same robot.
5. `FeatureEngineer` sorts each robot's rows by `time_step`, calls `feature_contract.build_features`, then retains simulator ground truth in the dataset row for replay/label use.
6. `main.py` removes rows with any missing deployable feature. The current five-observation windows require four previous observations, so the expected feature set has 96 rows per robot (9,600 total), covering steps 5–100.
7. The labeled and featured datasets are saved as `data/labeled_dataset.csv` and `data/feature_dataset.csv`. Manufacturer and robot type are normalized to strings.
8. `ReliabilityModel.train()` selects the 38-feature allowlist, performs a robot-group split, fits preprocessing and the Random Forest, prints record-level metrics, then separately trains the diagnosis model.
9. `main.py` wraps the in-memory estimators in `PredictionEngine` / `DiagnosisEngine` and runs simulated ingestion and replay.

**Persistence:** the current main path does not serialize either fitted estimator. `train_model.py` contains no model save call, and `PredictionEngine` receives a live model object. The repository contains no `.pkl`, `.joblib`, `.pickle`, or `.onnx` model artifact. The deployable artifact path is therefore **none**.

### Flow summary

```text
FleetSimulator hidden state + synthetic telemetry + actual event flags
  → DatasetGenerator raw trajectory rows
  → LabelGenerator future-10-observation risk and diagnosis labels
  → FeatureEngineer / feature_contract (same ordered feature definitions as streaming)
  → main.py complete-feature filter
  → ReliabilityModel: robot-group split, train-only preprocessing, Random Forest
  → in-memory PredictionEngine.predict / predict_batch
```

`feature_engineering.py` keeps simulator ground truth in the output record, but `train_model.py` takes `X` only from `DEPLOYABLE_FEATURES`; those ground-truth fields do not enter the risk classifier's feature matrix.

## 3. Dataset structure

### Audited local training files

The configured source pair (`raw_dataset_v2.csv` → `labeled_dataset.csv` → `feature_dataset.csv`) contains:

| Dataset | Rows | Robots | Rows per robot | Notes |
|---|---:|---:|---:|---|
| `raw_dataset_v2.csv` | 10,000 | 100 | 100 | Simulator output with failure events and electrical telemetry |
| `labeled_dataset.csv` | 10,000 | 100 | 100 | Risk and future failure-type labels |
| `feature_dataset.csv` | 9,600 | 100 | 96 | Four-observation warm-up removed; steps 5–100 |

The raw/labeled records align at every `(robot_id, time_step)` for manufacturer, robot type, motor temperature, battery level, event flag, and failure type. Recomputing feature outputs matches all **364,800** saved feature-cell comparisons (9,600 rows × 38 features). Saved label files predate unknown-target persistence and therefore retain the pre-correction labels; the updated generator now emits the corrected targets.

The saved raw/labeled dataset represents these populations:

| Attribute | Distribution |
|---|---|
| Manufacturers | Manufacturer_A 4,000 rows; Manufacturer_B 2,400; Manufacturer_C 3,600 |
| Robot types | AMR 3,600 rows; Humanoid 3,600; Robotic_Arm 2,800 |
| Trajectory coverage | 100 robots × 100 consecutive time steps |
| Actual failure events | 66 event rows: 49 thermal, 17 battery |
| Robots with at least one event | 43 of 100 (66 events across 43 robots means some trajectories contain repeat events) |

The pre-correction saved `feature_dataset.csv` contains 9,600 complete-feature rows and stores 8,940 negative / 660 positive labels, with 490 thermal / 170 battery positive failure-type labels. Those old labels include censored rows. Under the corrected deterministic main generation path, the 10,000 raw rows yield **9,000 eligible labels: 8,388 negative / 612 positive**, plus **1,000 unknown**. After removing the four feature warm-up rows per robot, 9,600 rows have complete features: **8,600 are training eligible (7,988 negative / 612 positive), and 1,000 have unknown targets**. The saved CSV has all three robot types and manufacturers represented. `robot_id` and `time_step` are dataset metadata, not model inputs.

### Horizon audit

The current labeler creates 9,000 horizon-valid and 1,000 horizon-invalid rows in the 10,000-row dataset. After removing the 400 warm-up rows, all 1,000 invalid tail rows remain in the feature dataset (steps 91–100 for every robot). Before this correction, 952 had label 0 and 48 had label 1; **after correction all 1,000 have unknown (`None`) risk and diagnosis labels**. An observed event inside a partial horizon no longer makes the row eligible for the fixed-ten-observation target.

The local saved `labeled_dataset.csv` predates persistence of `horizon_valid` / `future_observations`. A fresh normal run includes those fields and the unknown targets. `supervised_training_eligibility_mask()` in `label_generator.py` is used by normal risk training, validation risk training, and diagnosis training. The normal risk path fails closed if `horizon_valid` is absent.

Other `*_v2.csv` files also exist. The `*_v2` labeled/feature files are not the paths used by the current `main.py` configuration; they were not mixed into the counts above.

## 4. Label generation

`LabelGenerator.create_labels()` (`label_generator.py`) groups rows by `robot_id` and sorts each trajectory by numeric `time_step` when available. For each row it examines `records[index + 1 : index + 1 + prediction_window]`; the default window is 10 **following rows**, not the current row. It checks only `failure_event`, deliberately not the persistent `failure_type` field.

| Target | Condition | Timing relative to actual event | Future information? |
|---|---|---|---|
| Risk `label=1` | At least one actual `failure_event` appears in the next 1–10 rows | Before the event, within the forecast window | Yes, by design: this is a future-event target |
| Risk `label=0` | No event appears in the inspected future rows | Only a conclusive negative if all 10 future rows exist | Yes; rows without all 10 are marked `horizon_valid=False` |
| Risk `label=None` | Fewer than 10 future rows exist | Trajectory tail; outcome for the full horizon is unknown | Not a supervised target; row is retained but ineligible |
| Diagnosis `failure_type_label=thermal/battery` | The first actual future event in the window has that type | Before the event, within the same forecast window | Yes, by design |
| Diagnosis `failure_type_label=none` | No event appears in the inspected future rows | Conclusive only with a complete horizon | Same censoring issue as risk negatives |
| Diagnosis `failure_type_label=None` | Fewer than 10 future rows exist | Trajectory tail; future type within the full horizon is unknown | Not used for diagnosis fitting |

Because the current row is not examined, the exact failure-event row is normally label 0 unless another failure event occurs in its following window. Rows after a single event likewise become negative unless another event is forthcoming. This matches an **upcoming event** target, but it is not a current-failure detector target.

The labeler sorts each robot by numeric `time_step` when available; otherwise it preserves input order. A gapped or irregularly sampled trajectory is labeled by the next ten rows, not by elapsed time.

## 5. Leakage analysis

### Direct leakage controls verified

The ordered risk feature set excludes every field in `SIMULATOR_ONLY_FIELDS`: `battery_health`, `battery_stress`, `degradation_level`, `health`, `initial_health`, `failure_event`, `failure_type`, `recovery_event`, `label`, and `failure_type_label`. It also excludes robot identity and absolute timestep. Training selects by explicit allowlist rather than by dropping a blacklist.

### Indirect coupling / shortcut risk

This is **not a direct leak of the current row's event flag into X**. Risk labels depend on future event flags. However, the simulator makes the observable feature trajectories structurally close to the rules that create those events:

* **Thermal:** by default, thermal failure occurs when observed `motor_temperature` reaches the configured 80°C threshold. Motor temperature itself includes degradation heat scaled from hidden `degradation_level`; `thermal_rise`, temperature rates, averages, maxima, acceleration, and persistence all re-express that same simulated temperature trajectory. The failure uses the observed temperature by default, so the feature/condition relationship is especially direct.
* **Battery:** failure requires hidden `battery_health <= 0.70`, hidden `battery_stress >= 5.0`, and observable `battery_level <= 35.0`. Battery level is therefore explicitly one part of the failure rule. Battery current, voltage drop/voltage, and battery temperature are also generated from hidden battery health/stress and workload. The temporal battery features repeat those proxies.
* **Workload:** workload drives heat, battery consumption, and battery stress. The simulator maps low/medium/high to exactly 25/55/85, and the default workload cycle is synchronized across robots. Workload/power/current can therefore reveal simulator operating phase and failure progression.

These relationships can let the model recognize a simulator signature rather than learn a robust, sensor-independent reliability pattern. They are **LEAKAGE / DATA / FEATURE risks**, not evidence that the feature allowlist contains simulator-only columns. The existing validation harness has scenario/seed tests, but no fitted artifact is available here to determine actual model dependence or performance.

## 6. Train/test methodology

### Normal risk training (`ReliabilityModel.train`)

* `prepare_data()` first applies the shared horizon/known-target eligibility mask, then takes `y` from those eligible rows.
* `X` is exactly the eligible rows' `DEPLOYABLE_FEATURES`; rows with missing feature values are removed afterward.
* `robot_id` supplies `groups`; it is not included in X.
* `GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)` assigns whole robot groups to train or test. A given robot's time steps cannot occur on both sides.
* The estimator pipeline fits `OneHotEncoder(handle_unknown="ignore")` for manufacturer and robot type and passes numerical columns through. The preprocessor is fit by the pipeline on `X_train`, not on held-out X. No scaling is applied.
* Normal risk training requires `horizon_valid` and applies the shared `supervised_training_eligibility_mask()` before constructing the feature matrix.

This is a useful robot-identity holdout, but not a chronological holdout: train and test robots contain observations from the same time-step range, generated under the same simulator rules and global seed/configuration. It is a single split, not repeated grouped cross-validation or a held-out simulator configuration test. Record-level metrics treat correlated points within each test trajectory as individual observations.

### Diagnosis training

`train_diagnosis_model()` selects eligible risk-positive rows with non-`none` `failure_type_label`, uses the explicit `DIAGNOSIS_FEATURES` list (the same 38 deployable features), and performs a separate 80/20 robot-group split with random state 42. It uses the same eligibility selector as risk training.

### Validation-only fit path

`fit_for_validation()` uses the same eligibility selector as normal risk training and diagnosis training. The validation harness uses independently seeded robot IDs and held-out seed/scenario datasets. Its tests assert disjoint train/test robot IDs and censored-row exclusion. No validation metrics were recalculated in this audit.

## 7. Current Random Forest configuration

| Property | Failure-risk model | Diagnosis model |
|---|---|---|
| Estimator | `RandomForestClassifier` | `RandomForestClassifier` |
| Trees | 100 | 100 |
| `class_weight` | `balanced` | `balanced` |
| `random_state` | 42 | 42 |
| Other RF settings | scikit-learn defaults (including `max_depth=None`) | scikit-learn defaults |
| Target | `label`, classes 0/1 | `failure_type_label`, expected classes thermal/battery |
| Input feature count | 38 | 38 |
| Preprocessing | One-hot manufacturer/type; numeric passthrough | Same |
| Probability / class output | `predict_proba`, column index 1, rounded to 4 decimal places | Diagnosis uses `classifier.predict()` for the class; the separately reported diagnosis confidence is a heuristic based on counted evidence, not the classifier's probability |
| Artifact path | None; in-memory only | None; in-memory only |

Risk training reports classification metrics, confusion matrix, ROC-AUC, false positive/negative counts, and feature importances. `main.py` also performs record-level evaluations and warning/lead-time experiments. This audit did not run any of those model evaluations because no fitted artifact was available and the runtime lacks scikit-learn.

The risk prediction label returned by `RandomForestClassifier.predict()` uses its default decision rule; `PredictionEngine` does not add a separate tuned probability threshold. The train/test split seed and estimator seed are both fixed at 42.

## 8. Audit of the 38 deployable features

Categories: **DIRECT_SENSOR** = current numeric telemetry value; **DERIVED_SENSOR** = instantaneous calculation from current measurements; **TEMPORAL** = history-derived; **CONTEXTUAL** = identity or operating context. “Real availability” below is an engineering plausibility assessment, not a claim of vendor-wide support.

| # | Feature | Class | Definition / simulator relationship | Real telemetry plausibility and audit note |
|---:|---|---|---|---|
| 1 | `manufacturer` | CONTEXTUAL | Robot manufacturer string | Usually obtainable from fleet inventory; not a sensor. Unknown categories are ignored by the encoder. |
| 2 | `robot_type` | CONTEXTUAL | Robot type string | Usually obtainable from fleet inventory; taxonomy may differ across integrations. |
| 3 | `motor_temperature` | DIRECT_SENSOR | Current motor temperature; simulator adds workload heat, hidden degradation coupling, cooling, spikes, and noise | Plausible only when that robot exposes a motor sensor with known units/location. Directly tied to the thermal failure signature in this simulator. |
| 4 | `ambient_temperature` | DIRECT_SENSOR | Current ambient temperature; simulator uses a bounded random walk | Plausible if a robot/environment sensor is available; placement and calibration vary. |
| 5 | `thermal_rise` | DERIVED_SENSOR | `motor_temperature - ambient_temperature` | Deployable when both source sensors are valid and synchronized. Mathematically duplicates those two measurements. |
| 6 | `temperature_change` | TEMPORAL | Current motor temperature minus previous observation | Deployable with ordered, regularly timed history; highly overlaps rates/acceleration. |
| 7 | `temperature_rate_3` | TEMPORAL | Current minus motor temperature 3 steps earlier | Deployable if samples arrive consistently; simulator heat includes hidden degradation. |
| 8 | `temperature_rate_5` | TEMPORAL | Current minus value 4 steps earlier (five samples including current) | Deployable with fixed sample cadence; overlaps temperature change and other trend summaries. |
| 9 | `temperature_avg_3` | TEMPORAL | Three-sample motor-temperature average including current | Deployable with history; correlated with current temperature and longer average. |
| 10 | `temperature_avg_5` | TEMPORAL | Five-sample motor-temperature average including current | Deployable with history; correlated with other thermal windows. |
| 11 | `thermal_rise_rate_3` | TEMPORAL | Current thermal rise minus value 3 steps earlier | Deployable from motor/ambient history; proxies simulator degradation trajectory. |
| 12 | `battery_level` | DIRECT_SENSOR | Current simulated battery percentage | Common telemetry concept, but units/semantics vary. It is explicitly part of the battery failure rule (`<=35`). |
| 13 | `battery_voltage` | DIRECT_SENSOR | Current battery voltage, generated from nominal voltage less simulated stress/health drop | Common when exposed by the BMS; tightly coupled to hidden simulated battery state. |
| 14 | `battery_current` | DIRECT_SENSOR | Current, increased by simulated workload and battery degradation | Common on some BMS/drive systems; sample and direction semantics can vary. |
| 15 | `battery_temperature` | DIRECT_SENSOR | Current battery temperature, generated from ambient, current and hidden health | Available only on instrumented packs; simulator embeds hidden health coupling. |
| 16 | `power_consumption` | DIRECT_SENSOR | Current simulator value is voltage × current | Often derived rather than independently sensed; exactly redundant with voltage/current in this simulator apart from rounding. |
| 17 | `voltage_drop` | DERIVED_SENSOR | Simulator-provided drop from nominal voltage, battery stress and health | Requires a defined nominal/reference voltage; not a portable raw sensor field. Strong hidden battery-state proxy. |
| 18 | `battery_change` | TEMPORAL | Current battery level minus previous value (decline is negative) | Deployable with history; overlaps positive decline/rate features. |
| 19 | `battery_drop_rate_3` | TEMPORAL | Battery level 3 steps earlier minus current (positive decline) | Deployable with fixed cadence; direct trend proxy for the battery failure rule. |
| 20 | `battery_voltage_change` | TEMPORAL | Current voltage minus previous value | Deployable with history; overlaps voltage decline/rate features. |
| 21 | `battery_voltage_drop_rate_3` | TEMPORAL | Voltage 3 steps earlier minus current | Deployable with history; correlated with voltage drop and battery health/stress. |
| 22 | `battery_current_change` | TEMPORAL | Current battery current minus previous value | Deployable with history; correlated with current and the 3-step change. |
| 23 | `battery_temperature_change` | TEMPORAL | Current battery temperature minus previous value | Deployable with history where pack temperature is instrumented. |
| 24 | `battery_temperature_rate_3` | TEMPORAL | Current battery temperature minus value 3 steps earlier | Deployable with history; overlaps battery-temperature change. |
| 25 | `power_change` | TEMPORAL | Current power minus previous value | Deployable if power is present/derived consistently; overlaps voltage/current changes. |
| 26 | `power_rate_3` | TEMPORAL | Current power minus value 3 steps earlier | Deployable with history; redundant with voltage/current trajectories. |
| 27 | `workload` | CONTEXTUAL | Simulator maps low/medium/high categorically to 25/55/85 | A workload/utilization signal is plausible, but this exact numeric encoding is simulator-specific and its equal spacing is artificial. |
| 28 | `thermal_rise_max_3` | TEMPORAL | Maximum thermal rise in three samples including current | Deployable with history; overlaps current thermal rise and averages. |
| 29 | `thermal_rise_max_5` | TEMPORAL | Maximum thermal rise in five samples including current | Deployable with history; overlaps 3-sample maximum and averages. |
| 30 | `thermal_rise_avg_3` | TEMPORAL | Three-sample thermal-rise average including current | Deployable from the same two temperature channels; redundant with temperature averages/current rise. |
| 31 | `thermal_rise_avg_5` | TEMPORAL | Five-sample thermal-rise average including current | Deployable with history; overlaps other thermal summaries. |
| 32 | `thermal_elevated_persistence` | TEMPORAL | Consecutive observations with thermal rise at least 20°C, including current | Deployable with history; embeds a fixed simulator/engineering cutoff in a model feature. |
| 33 | `temperature_acceleration` | TEMPORAL | Current temperature change minus prior temperature change | Deployable with regular history; amplifies noise and overlaps other thermal trend features. |
| 34 | `battery_decline_3` | TEMPORAL | Battery level 2 rows earlier minus current over a three-sample window | Deployable; duplicates the same direction of battery-level movement as `battery_drop_rate_3` at a different lag. |
| 35 | `battery_decline_5` | TEMPORAL | Battery level 4 rows earlier minus current over a five-sample window | Deployable; overlaps battery drop rate and the 3-sample decline. |
| 36 | `low_battery_persistence` | TEMPORAL | Consecutive battery readings at or below 35, including current | Deployable with history; the cutoff is exactly the simulator battery failure-level condition. |
| 37 | `battery_voltage_decline_3` | TEMPORAL | Voltage 2 rows earlier minus current over a three-sample window | Deployable with history; overlaps voltage change/drop features. |
| 38 | `battery_current_change_3` | TEMPORAL | Current battery current minus its value 2 rows earlier over a three-sample window | Deployable with history; overlaps current change and power change. |

### Redundancy and real-world availability

* **Thermal redundancy:** motor temperature and thermal rise are algebraically linked; temperature point changes, 3/5-step deltas, acceleration, averages, maxima, and persistence summarize heavily overlapping trajectories.
* **Battery redundancy:** battery level change/drop/decline windows duplicate direction and lag; voltage change/drop/decline overlap; battery current change overlaps power change because simulator power is voltage × current.
* **Simulator proxies:** all direct observations are generated from known hidden simulator states through hand-written formulas; especially motor temperature/thermal rise for degradation and voltage/current/temperature/level for battery health/stress.
* **Potential availability gaps:** battery temperature/current/voltage and ambient temperature are not universal across real robots; workload may not exist in a shared numeric scale; power and voltage-drop may be derived under different nominal-voltage conventions. The streaming feature contract correctly requires four prior observations for full readiness, but the model still presumes every allowlisted current channel is present.

No feature is literally a simulator-only hidden field. Several features are plausible real telemetry, but data availability, units, cadence, and sensor reliability must be verified per robot family before deployment.

## 9. Synthetic realism audit

### Concrete simulator properties that shape this learning task

* Failure mechanism is selected once per trajectory with weights **none 0.60 / thermal 0.20 / battery 0.20**. The resulting population has only two failure classes and one chosen mechanism per robot (though the simulator can emit repeated event rows after a recovery path).
* Thermal degradation uses a small set of explicit schedules: gradual `+0.08` each step; sudden changes from `+0.03` to `+0.30` at step 40; intermittent bursts at steps 25–35 and 60–70. Thermal observation coupling is a configurable multiplier on degradation level. Thermal failure defaults to observed motor temperature `>=80°C`.
* Thermal telemetry has non-zero random noise (default ±1.5°C) and occasional spikes (5% chance, 3–10°C at default scale), so this is **not a no-noise simulator**. Ambient temperature also varies, within a bounded 18–42°C range.
* Battery failure is a clean conjunction of fixed health, stress and battery-level cutoffs. Battery health/stress evolve from a per-trajectory degradation rate, workload and failure mechanism. Battery voltage drop/current/temperature formulas explicitly depend on those hidden variables.
* Default workload changes on a four-value low/medium/high/medium schedule every 20 steps. It is synchronized across robots by default, although initial workload is randomized and the simulator supports alternate workload modes.
* Robot identities/types/manufacturers, initial health, ambient temperature, random telemetry and battery degradation rate do vary. Thus trajectories are not identical. However, the failure thresholds/equations and thermal pattern families are shared across the population; there is no evidence of real robot-specific threshold/calibration variation.
* The simulator code has stochastic sensor noise and environmental variation, but the default data path does not simulate sensor dropout/missingness, calibration drift, sampling gaps, or field communication faults.
* `main.py` seeds the global PRNG with 42. Its default `DatasetGenerator` call does not pass its own seed, so the normal regenerated training dataset is repeatable from that global seed rather than an independent fresh seed on each run.

### Audit judgment

The principal realism concern is not “synthetic data is bad”; it is that the equations create narrow, explicit telemetry signatures from the same latent variables and fixed thresholds used to generate failure labels. Paired with a single fixed-seed normal training run, this permits strong in-distribution learning without demonstrating robustness to different robot physics, sensing stacks, or degradation/failure relationships. Existing `validation_experiment.py` has separate seeds and parameter/workload scenarios, including telemetry stress, but no fitted-model results can be inspected here.

## 10. Missing artifact and environment limitations

* No fitted model artifact is present in the repository; `main.py` trains in memory and does not save one.
* The available Python runtime cannot import `scikit-learn`. ML training/evaluation tests and model metric reproduction therefore cannot run in this environment.
* This audit and correction use source inspection, CSV analysis, label generation, and feature recomputation only. No estimator was fitted; no accuracy, ROC-AUC, feature importance, or real-world performance is reported.
* Stored `feature_dataset.csv` matches current `FeatureEngineer` output on its 38 allowlisted feature cells. Stored label files predate the unknown-target correction and omit horizon metadata; the default `main.py` path regenerates labels and writes updated files. This correction does not alter feature values or fit a model.

## 11. Findings and classifications

| Classification | Finding | Evidence / importance |
|---|---|---|
| **LABEL — corrected** | Incomplete target horizons are unknown and excluded from all supervised fits. | `LabelGenerator` writes `None` when fewer than ten future rows exist; normal risk, validation risk, and diagnosis training share one horizon-and-binary-target selector. Regression tests cover censored rows and eligibility. |
| **LEAKAGE** | The observable features are structurally coupled to the future failure rules. | Motor temperature is the default thermal failure measurement; battery level is a failure conjunct; other battery channels use hidden health/stress. This is indirect target-proxy leakage, not a forbidden simulator field in X. **High risk to generalization.** |
| **DATA** | The normal model is trained on one repeatable synthetic population and shared simulator mechanics. | `main.py` seeds 42; default thresholds, workload schedule and equations are common across robots. Existing validation source provides alternate seeds/configs, but no fitted results are available. |
| **FEATURE** | Multiple features are highly redundant and some semantics are simulator-specific. | Algebraic thermal rise; overlapping thermal windows; duplicate battery level/voltage/current trends; power is voltage × current; workload encoding is 25/55/85; low-battery persistence cutoff matches the failure rule. |
| **DATA** | Missingness and field telemetry faults are not represented in the default simulator path. | Noise/spikes and ambient movement exist, but no dropout/calibration/cadence faults. Observation-quality tests do not show that the training dataset covers those faults. |
| **NONE** | Direct simulator-state/ground-truth fields are absent from the explicit risk allowlist. | Verified 38-feature `DEPLOYABLE_FEATURES` does not intersect `SIMULATOR_ONLY_FIELDS`; robot ID and timestep also excluded. |
| **NONE** | Robot identity leakage across the normal risk train/test split is controlled. | `GroupShuffleSplit(groups=robot_id)` keeps all rows of a robot on one side; the preprocessing pipeline is fit on training rows. |

## 12. Recommended next experiments

1. **Fixed-horizon baseline:** when scikit-learn is available, retain the current estimator and features; fit/evaluate only newly eligible records. Use grouped robot holdout and report excluded censored-row counts. The eligibility correction is implemented; this experiment should evaluate its effect without changing model design.
2. **Independent seed generalization:** train on independent training seeds and evaluate on held-out seeds, keeping robot IDs disjoint and recording group-level as well as record-level metrics.
3. **Failure coupling challenge:** keep the fitted model fixed while changing failure thresholds/coupling as the existing validation harness specifies. Report whether risk probability remains calibrated and whether event warnings occur before failure.
4. **Feature-family ablation:** compare thermal, battery, and workload groups only after a reproducible baseline is available. Keep splits and labels fixed; examine probability behavior and event lead time, not accuracy alone.
5. **Sensing robustness:** add controlled dropout, cadence gaps, and sensor noise/calibration shifts to evaluation telemetry without changing labels or the production model. Report observation-quality outcomes separately from risk scores.

No experiment was run here that fits or evaluates a model.

## 13. Remaining prioritized improvement backlog

### A. DATA

1. Obtain time-aligned real telemetry and confirmed maintenance/failure events for at least several robot populations; document sensor units, cadence, and availability.
2. Add evaluation-only missingness, calibration drift, sampling gaps, and robot-specific operating variability to simulator scenarios.
3. Separate generated training seeds from held-out evaluation seeds and scenario configurations; preserve source/config metadata with each dataset.

### B. LABEL

1. **Completed in this correction:** exclude invalid horizons and unknown targets from risk and diagnosis fitting through the shared selector. Apply the same eligibility rule to future fixed-horizon metrics.
2. Document the target as “an event in the next ten observations” and separately measure warning lead time to an actual event.
3. Verify contiguous timestamps and one consistent event definition before labeling imported data.

### C. FEATURE

1. Measure grouped/seed-held-out value of correlated feature families before removing or adding any feature.
2. Validate workload encoding and voltage-drop/power derivations against each real robot schema.
3. Audit the embedded 20°C thermal-persistence and 35% low-battery cutoffs as simulator-linked feature semantics; do not alter them without a controlled comparison.

### D. TRAINING

1. Make normal training and validation share the same horizon-validity policy.
2. Report per-robot and per-failure-type counts in every split; repeat grouped splits or use held-out seeds to quantify variance.
3. Define an explicit versioned artifact location and metadata (feature schema, training seeds/configs, label horizon, estimator settings) before deployment needs one.

### E. MODEL

1. Keep the current Random Forest as the baseline until data/label and validation issues are resolved.
2. Only then compare simple baselines or calibrate probabilities, using the same grouped/sequential evaluation; do not optimize accuracy alone.

### F. EVALUATION

1. Report precision/recall/F1, ROC-AUC, PR-AUC, Brier score/calibration, confusion matrix, and class prevalence.
2. Report event-level detection coverage, false alarms per robot-time, and lead-time distribution alongside record-level metrics.
3. Include seed, robot-group, workload, failure-parameter, and sensing-quality shifts; state clearly when a test does not represent independent physical robots.

## Evidence sources inspected

`dataset_generator.py`, `fleet_simulator.py`, `label_generator.py`, `feature_engineering.py`, `feature_contract.py`, `train_model.py`, `prediction_engine.py`, `main.py`, `test_feature_contract.py`, `test_diagnosis_contract.py`, `test_validation_harness.py`, `validation_experiment.py`, and the local `raw_dataset_v2.csv`, `labeled_dataset.csv`, and `feature_dataset.csv` files.

### Source locations for the main audit claims

* Fixed-seed and current generation settings: `main.py:41-51`, `main.py:118-160`, `main.py:1075-1090`.
* Dataset simulation/export: `dataset_generator.py:8-26`, `dataset_generator.py:29-98`; failure mechanism selection and rules: `fleet_simulator.py:4-18`, `fleet_simulator.py:201-220`, `fleet_simulator.py:266-297`, `fleet_simulator.py:350-423`, `fleet_simulator.py:445-550`, `fleet_simulator.py:635-717`.
* Future labels, chronological per-robot windows, unknown targets, and shared eligibility: `label_generator.py:1-112`.
* Ordered 38-feature allowlist and simulator-only deny set: `feature_contract.py:27-122`; formulas and feature result: `feature_contract.py:230-312`; batch chronology and preserved labels: `feature_engineering.py:9-40`.
* Risk schema/split/Random Forest: `train_model.py:43-142`; validation shared eligibility: `train_model.py:145-213`; diagnosis schema/split/eligibility: `train_model.py:216-278`.
* Streaming schema order and probability output: `prediction_engine.py:8-98`.
* Grouped seed/scenario validation definitions: `validation_experiment.py:15-87`; grouped/censored assertions: `test_validation_harness.py:25-86`.
