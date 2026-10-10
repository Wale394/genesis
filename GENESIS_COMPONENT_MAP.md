# Genesis Component Map

This map reflects files present in the inspected checkout. Layer values are also represented in `architecture_contract.py`.

## Current runtime and supporting components

| File | Layer | Role / boundary |
|---|---|---|
| `ros2_telemetry_adapter.py` | Data ingestion | Translates ROS-like diagnostic messages into Genesis-shaped observations; no ROS dependency or control behavior. |
| `robot_adapter.py` | Data ingestion | Adapter abstraction and simulated adapter. |
| `history.py` | Data ingestion | Stores telemetry/history and incident references for pipeline use. |
| `normalizer.py` | Normalization | Normalizes raw aliases, units, and states. |
| `telemetry.py` | Normalization | Creates telemetry snapshots from normalized data. |
| `feature_contract.py` | Normalization | Authoritative deployable derived-feature definitions and allowlists. |
| `telemetry_features.py` | Normalization | Stateful per-robot streaming builder over the feature contract. |
| `robot.py`, `robot_profile.py` | Robot identity/profile | Robot state object and operating profile thresholds. |
| `observation_quality.py` | Analysis | Assesses telemetry availability/trustworthiness. |
| `telemetry_pattern_engine.py` | Analysis | Describes observed temporal patterns; no causal or lifecycle authority. |
| `reliability_signal.py` | Analysis | Emits engineering signals from observable records. |
| `prediction_engine.py`, `diagnosis_engine.py` | Analysis | Risk and failure-type model inference wrappers. |
| `risk_engine.py` | Analysis | Coordinates available risk evidence for the pipeline. |
| `fleet_baseline.py` | Analysis/context evidence | Peer comparison context; does not set state. |
| `comparison_engine.py`, `baseline_engine.py` | Analysis/context evidence | Historical comparison/baseline calculations. |
| `pattern_detector.py` | Analysis/context evidence | Incident/diagnosis recurrence patterns; not the telemetry trajectory engine. |
| `reliability_memory.py` | Memory | In-memory incident knowledge persistence and retrieval. |
| `evidence_synthesis.py`, `evidence_engine.py`, `evidence_timeline.py` | Evidence | Structured source evidence and timeline. |
| `incident_explanation.py` | Evidence | Human-readable investigation explanation builder. |
| `incident.py`, `reliability_event.py` | Incident lifecycle data | Incident/event records. |
| `incident_manager.py` | Incident lifecycle | Owns incident create/update/fail/recover/close operations. |
| `reliability_fusion.py`, `reliability_state.py` | Decision | Existing evidence fusion and state transitions. |
| `recommendation_engine.py` | Decision | Existing recommendation rules. |
| `warning_engine.py` | Decision | Warning evaluation. |
| `decision_pipeline.py` | Decision orchestration | Coordinates current analysis, state, incident, memory, and evidence components. |
| `genesis.py` | Interface/platform | Public `Genesis` investigation facade. |
| `genesis_cli.py` | Interface/platform | Human and JSON output rendering. |
| `demo_genesis_investigation.py`, `main.py` | Interface/platform/demo | Demo and full development pipeline entry points. |

## Offline training and validation

| Files | Boundary |
|---|---|
| `fleet_simulator.py`, `dataset_generator.py`, `label_generator.py`, `feature_engineering.py`, `train_model.py` | Simulated dataset generation, labels, shared feature preparation, and model training. Not streaming runtime inference. |
| `validation_experiment.py`, `validation_factorial.py`, `failure_investigation.py`, `inspect_false_warning.py`, `inspect_validation_probabilities.py` | Offline validation and diagnostic experiments. They may inspect simulator truth for evaluation; that truth is not deployable telemetry. |
| `data/` | Generated datasets and validation artifacts; data files are not code components. |
| `ML_EVALUATION_V0_1.md` | Evaluation documentation. |
| `analyzer.py` | Legacy rule-based analysis/demo, not the current pipeline. |

## Tests

`test_*.py` files are validation infrastructure, not runtime architecture. The repository includes tests for decision pipeline, evidence, feature contracts, diagnosis, fleet baselines, fusion, Genesis API/CLI, incident explanation, labels, observation quality, reliability memory/signals, ROS adapter, telemetry patterns, and validation harness behavior.

## Field-test component status

The inspected repository contains **none** of `field_test_session.py`, `field_test_config.py`, `field_test_runner.py`, `field_test_report.py`, or `genesis_field_test.py`. The machine-readable contract records these as `NOT_IMPLEMENTED` planned boundaries in the `field_test_data_infrastructure` layer. No current component-map row should be read as claiming that field-test infrastructure exists.

## Ownership constraints

- `IncidentManager` owns incident lifecycle operations.
- `RecommendationEngine` owns recommendation generation.
- `EvidenceSynthesis` assembles evidence; it does not transition state or lifecycle.
- `TelemetryPatternEngine` describes telemetry patterns; it does not infer diagnosis/cause, score risk, or manage incidents.
- `FleetBaseline` produces peer context; it does not set reliability state.
- `ReliabilityMemory` stores and retrieves context; it does not recommend actions.
- `Genesis` is the public interface/coordinator; the CLI renders its structured result.
- ROS 2 ingestion translates telemetry and has no control behavior.
- Future field-test modules should capture data/session metadata and call the same Genesis interfaces, not duplicate reasoning.

