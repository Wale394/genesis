# Genesis Core Boundary v0.1

**Status:** Architecture definition only. Robotics remains Genesis's current domain and proving ground. No refactor or runtime behavior change is proposed.

## Boundary decision

The smallest practical split is:

- **Genesis Core:** reusable mechanisms and records for ordered observations/history, quality findings, temporal comparison, provenance-bearing evidence, incident/action/outcome records and memory.
- **Robotics Domain:** meanings of robot observations, states, failures, signals, peer groups, models/diagnoses and safe recommendations.
- **Interface / Adapter:** translate ROS 2, robot logs or other external payloads into the active domain's canonical observations while retaining source/time/unit/limitations. Translation does not assess reliability.

This is a conceptual ownership map, not a file-movement task. Current modules cross these boundaries.

## A. Genesis Core candidates

| Candidate | Why it belongs | Current domain assumptions | Reusable today? | Eventual change |
|---|---|---|---|---|
| Observation/history | Ordered measurements and source/time enable analysis. | Public record requires robot_id and fixed robot fields; builder history is per robot. genesis.py:188-230; telemetry_features.py:9-55 | History mechanism yes; schema no. | Define small explicit observation boundary only when needed; identity remains domain-supplied. |
| Observation quality | Missingness, warm-up, invalid values, static sensors, jumps and disagreement affect evidence trust. | Hard-coded thermal/battery/workload groups and battery percentage bound. observation_quality.py:23-67, 126-190 | Check mechanics yes; field rules no. | Domain declares fields, groups, bounds and applicable checks. |
| Time/sampling context | Timestamp/cadence comparison is generally useful and avoids claiming gaps without context. | Uses time_step; facade may assign ingestion-order fallback. telemetry_sampling_context.py:12-124; genesis.py:103-119 | Largely yes. | Keep source timestamp distinct from sequence index; specify normalized time semantics. |
| Temporal comparison | Difference/rate/window/persistence operations recur across systems. | Feature contract and comparison metrics are robot-specific; baseline eligibility uses health/failure_event. feature_contract.py:8-73; comparison_engine.py:1-64; baseline_engine.py:1-61 | Math yes; fields/eligibility no. | Reuse declared operations; do not universalize feature names or healthy criteria. |
| Pattern representation | Deterministic descriptions with window, measurements and provenance are useful evidence. | Thermal/battery/workload detectors; separate recurrence engine. telemetry_pattern_engine.py:20-45, 86-165 | Representation yes; detectors no. | Common representation, domain-owned definitions; keep pattern separate from cause. |
| Evidence/provenance | Sources, statements, support and limitations preserve observation/inference distinction. | Synthesis selects fields from robot feature contract. evidence_synthesis.py:7-35, 95-153 | Strong candidate; currently robot vocabulary. | Core accepts evidence records; domain producers own meanings. |
| Assessment | Structured interpretation can combine quality, evidence and inference. | Fusion/state embeds robot limits and fixed risk bands. reliability_fusion.py:19-99; reliability_state.py:1-42 | Record/orchestration yes; policy no. | Domain policy owns risk/state interpretation; no universal score. |
| Incident lifecycle | Link observations, evidence, assessment, recommendations, action and outcome. | Incident/manager keyed by robot_id; robot failure/recovery transitions and simulator event fields. incident.py:1-45; incident_manager.py:43-95; decision_pipeline.py:63-71, 243-256 | Record/ownership yes; identity/transitions not neutral. | One lifecycle owner; domain defines relevant state/event meaning. |
| Memory | Store and retrieve prior event context. | Similarity uses robot/manufacturer/type, signals, diagnosis and state; simulator fields filtered. reliability_memory.py:8-29, 221-294 | Storage yes; retrieval keys domain-specific. | Keep storage common; explicit domain matching keys. |
| Explanation/report | Project collected evidence, limitations, action and outcome without rerunning inference. | Robot identity and motor-temperature trajectory in current report. incident_explanation.py:19-159; investigation_report.py:17-50, 247-267 | Projection yes; sections/content not. | Keep assembly separate from domain-specific presentation. |
| Recommendation lifecycle | Recording recommendation, action and outcome is reusable. | Actual rules prescribe robot workload/thermal/battery actions. recommendation_engine.py:17-149 | Lifecycle yes; action rules no. | Keep ownership; domain policy supplies permitted action and text. |

## B. Robotics Domain

Keep these explicitly robotics-specific:

- Robot identity/hierarchy: robot_id, type, manufacturer/model, firmware and site.
- Robot profiles and working/idle/failed states.
- Motor/ambient temperature, thermal rise, battery level/voltage/current/temperature, robot workload/state, power and voltage drop semantics.
- ReliabilitySignal rules and motor/battery/thermal/electrical limits.
- Thermal/battery/workload quality groups and telemetry patterns.
- Robot feature allowlists, failure horizon/labels, RF artifact, thermal-vs-battery diagnosis.
- Manufacturer/type robot-fleet grouping and robot baseline interpretation.
- Robot failure/recovery meaning and operator recommendations.
- ROS 2 robot telemetry mappings and read-only Field Agent session config.

These are not flaws because they are specific. The risk is letting their meanings leak into purportedly shared components or using them as another domain's implied contract.

## C. Interface / Adapter Layer

| Component | Interface responsibility | Translation/reasoning mixture or limitation |
|---|---|---|
| ros2_telemetry_adapter.py | Map ROS-like diagnostics, units, timestamp and source metadata; report ignored/invalid values. No ROS import or control API. | Maps directly to robot schema and robot_state. Robotics adapter by design. |
| robot_adapter.py | Abstract source retrieval; includes simulated robot adapter. | Robot-specific implementation. |
| genesis_field_agent.py | Compose config, ROS adapter, optional Genesis call and session capture; raw observations/results separate. | Robot identity/config and ROS-like source. Read-only. |
| genesis_field_agent_config.py, genesis_field_session_schema.json | Validate robot field-session config/output. | robot_id and supported telemetry are domain-specific. |
| normalizer.py | Canonicalize aliases and units/state spelling. | Also assumes robot-required fields and working/idle state; syntax translation plus robot schema validation, not neutral health assessment. |
| telemetry_capability_discovery.py | Inventory observed fields/quality/available analyses. | Robot telemetry catalog and thermal/battery capability names. |
| telemetry_sampling_context.py | Analyze source timestamp intervals. | Conceptually Core temporal evidence despite interface-supplied timestamps. |
| genesis.py public facade | Validate inputs, sequence, own histories/features and coordinate analysis. | More than an adapter: it owns per-robot state and full pipeline coordination. Current public facade is a robot API. |

**Boundary rule:** adapters translate payload shape, aliases, units, timestamps and source metadata; preserve unknowns/limitations; never create signals, diagnosis, reliability state, outcome or recommendation.

## 1. Boundary map

“Change needed now” is “No” throughout: this is analysis only. Categories describe conceptual ownership, not current code purity.

| Current Component | Current Location | Proposed Conceptual Boundary | Why | Change Needed Now? |
|---|---|---|---|---|
| Public facade/orchestrator | genesis.py | ROBOT DOMAIN | Robot input/output; coordinates the current robot pipeline. | No |
| Decision orchestration | decision_pipeline.py | CORE with domain policy dependencies | Sequence reusable, but currently reads robot/simulator semantics. | No |
| Observation quality | observation_quality.py | CORE mechanism + ROBOT DOMAIN field rules | Check mechanics recur; groups/bounds differ. | No |
| Sampling interval analysis | telemetry_sampling_context.py | CORE | Largely neutral timestamp/cadence evidence. | No |
| Feature contract/builder | feature_contract.py, telemetry_features.py | ROBOT DOMAIN | Fixed robot measurements/model schema; temporal arithmetic is reusable. | No |
| Telemetry pattern detector | telemetry_pattern_engine.py | ROBOT DOMAIN detector; CORE representation | Current pattern meanings are thermal/battery/workload. | No |
| Engineering signals | reliability_signal.py | ROBOT DOMAIN | Robot-specific fields and limits. | No |
| Fusion/state | reliability_fusion.py, reliability_state.py | CORE coordination + ROBOT DOMAIN policy | Flow can transfer; thresholds/state meanings cannot. | No |
| Evidence collection/synthesis | evidence_engine.py, evidence_synthesis.py | CORE mechanism + ROBOT DOMAIN producers/catalog | Provenance transfers; field taxonomy is robot-defined. | No |
| Timeline/explanation/report | evidence_timeline.py, incident_explanation.py, investigation_report.py | CORE record/projection + ROBOT DOMAIN content | Ordering/projection shareable; robot events/temperature are not. | No |
| Incident record/manager | incident.py, incident_manager.py | CORE lifecycle + ROBOT DOMAIN identity/event policy | Record/ownership transfer; ID and transitions are robot-shaped. | No |
| Memory | reliability_memory.py | CORE storage + ROBOT DOMAIN retrieval keys | Storage generalizes; robot similarity rules do not. | No |
| Historical comparison/baseline | comparison_engine.py, baseline_engine.py | ROBOT DOMAIN today; possible CORE math later | Fixed robot metrics; baseline uses simulator eligibility. | No |
| Peer/fleet comparison | fleet_baseline.py | ROBOT DOMAIN | Robot type/manufacturer cohorts and metrics. | No |
| Recommendation | recommendation_engine.py | ROBOT DOMAIN; CORE records lifecycle | Robot-specific actions. | No |
| Prediction/diagnosis | prediction_engine.py, diagnosis_engine.py | ROBOT DOMAIN; wrapper mechanics potentially CORE | Current schemas, labels and rules are robot-specific. | No |
| Robot model/profile | robot.py, robot_profile.py | ROBOT DOMAIN | Explicit robot concepts and limits. | No |
| ROS adapter | ros2_telemetry_adapter.py | INTERFACE | Translates ROS-like payload to robot telemetry. | No |
| Field Agent/config/schema | genesis_field_agent.py, genesis_field_agent_config.py, genesis_field_session_schema.json | INTERFACE | Captures read-only robot observations and optional results. | No |
| Source normalization | normalizer.py | INTERFACE + ROBOT DOMAIN validation | Alias/unit translation vs accepted robot fields/states. | No |
| Capability discovery | telemetry_capability_discovery.py | ROBOT DOMAIN analysis fed by INTERFACE | Inventories currently supported robot analyses. | No |
| Simulator/data/label/training | fleet_simulator.py, dataset_generator.py, label_generator.py, feature_engineering.py, train_model.py | SIMULATOR / OFFLINE | Generates synthetic data, targets, models and experiments. | No |
| Validation/investigation scripts | validation_experiment.py, validation_factorial.py, failure_investigation.py, inspect scripts | SIMULATOR / OFFLINE | Inspect simulated scenarios and ground truth. | No |
| Legacy analyzer/demos/CLI | analyzer.py, main.py, demo scripts, CLI | UNCERTAIN / interface or offline | Responsibilities differ; not the stable inference boundary. | No |

## 2. Minimum shared contracts

Current equivalents are dictionary-shaped and spread across modules; no single domain-neutral contract is used throughout.

| Concept | Minimum meaning | Existing equivalent | Assumptions and eventual requirement |
|---|---|---|---|
| Observation | Measured/observed value(s) at a time, subject, source, unit/representation, quality and metadata. | ROS adapter output, Genesis normalized record, Telemetry snapshot/feature record. | Current record requires robot_id and a fixed set of robot fields. Eventually separate source payload from canonical observations; retain domain identity. No generic Asset needed. |
| Evidence | Citable support for observation/inference, with category, source, statement, support and limitations. | EvidenceEngine/EvidenceSynthesis items and their source categories. | Some categories are robotics-specific. Preserve provenance; domain producers define semantics. |
| Pattern | Deterministic description of change across observations, window and supporting values. | TelemetryPatternEngine; pattern_detector for recurrence. | Representation can be shared; detectors/thresholds cannot. Pattern remains evidence, not cause. |
| Assessment | Structured interpretation of evidence, quality/limitations, model result and domain risk/state. | ReliabilityFusion, ReliabilityState, pipeline risk/quality results. | Current assessment folds robot signals and fixed bands. Domain owns interpretation; Core should not invent a universal score. |
| Incident | Lifecycle record linking observations/evidence/assessment/recommendation/action/outcome. | Incident and IncidentManager. | robot_id key and FAILED/RECOVERING semantics are current assumptions; neutral subject key is possible internally without Asset. |
| Outcome | What happened after event/action, with source/time and pending/unknown preserved. | Incident outcome, close, timeline outcome. | Pipeline also infers resolution from state and accepts simulator events. Eventually distinguish observed/confirmed outcome from inference and labels. |

A small envelope plus domain-owned measurement vocabulary is sufficient conceptually. Do not impose a universal sensor ontology.

## 3. Identity: retain robot_id for now

### Where it genuinely means a robot

- Public API input/output and Field Agent/ROS configuration identify a robot.
- FleetBaseline excludes the current robot and cohorts by robot_type/manufacturer.
- Robot profile, diagnosis, recommendations and report vocabulary refer to robot operation.
- ReliabilityMemory has explicit robot retrieval helpers and same-robot similarity.

### Where it is mainly a key

- TelemetryFeatureBuilder.history partitions temporal history.
- Genesis dictionaries partition accumulated records, capability observations, states and last timestamps by robot_id.
- IncidentManager selects active incidents by robot_id.
- History filters incidents by robot_id.
- Pipeline scopes pattern history/state/timeline to one robot.

These are subject-keyed storage operations in mechanism, although their present callers deliberately supply robot identity.

### Recommendation

**Do not replace robot_id with asset_id and do not create Asset now.** A second domain may need a component hierarchy, site/device tuple, session subject, or something else. Keep robot_id at the robotics boundary. If a real second domain arrives, let shared storage/lifecycle accept an opaque domain-supplied subject key and optional metadata; preserve robot_id, type/manufacturer/fleet and diagnosis as robotics-domain fields. Change only key-based internals proven to need generalization.

## 4. Baseline mismatch

### 1. Why the dependency exists
BaselineEngine selects only records where health == "healthy", excludes robot_state == "failed" and failure_event, then averages motor temperature, thermal rise and battery level. This is consistent with simulator trajectories that provide explicit healthy/failure ground truth.

### 2. Is it simulator leakage?
**Yes, in baseline eligibility.** health/failure_event are not deployable feature fields; failure_event is ground truth. This is not risk-model training leakage in this path; it is simulator knowledge embedded in a runtime-called contextual baseline.

### 3. Does it affect external telemetry?
**Yes.** Genesis passes accumulated TelemetryFeatureBuilder records into DecisionPipeline and BaselineEngine. The builder emits robot telemetry/derived values plus failure_event/recovery_event/failure_type placeholders as None, but does not emit health (telemetry_features.py:15-52). Therefore no record satisfies health == "healthy"; healthy_records remains empty and baseline remains insufficient_data, regardless of normal external history. Evidence synthesis receives this baseline status. This is missing context, not a fabricated prediction.

### 4. Smallest safe eventual correction
Do not remove the health filter and assume all history is healthy. Add an explicit baseline-eligibility input/policy owned by Robotics: only explicitly approved/observable, quality-acceptable reference records enter; absent qualification remains INSUFFICIENT_DATA with a reason. Preserve aggregation and output shape initially.

### 5. Fix or defer?
**Defer implementation in this analysis-only task.** This is worth addressing before relying on field baseline context, but changing eligibility silently risks including degraded operation. Specify and test eligibility first.

## 5. Current and proposed data flow

### Current implementation

~~~text
External ROS-like diagnostics / recorded robot data
        ↓
ROS2TelemetryAdapter (ROS keys/units → robot telemetry + source metadata)
        ↓
Genesis facade + Normalizer
  (robot_id required; robot fields/states; fallback time_step if no source time)
        ↓
TelemetryFeatureBuilder + robot feature_contract
  (per-robot history, formulas, warm-up)
        ↓
DecisionPipeline: quality + robot patterns + fleet comparison
        ↓
optional robot PredictionEngine + ReliabilitySignal
        ↓
ReliabilityFusion → ReliabilityState
        ↓
robot DiagnosisEngine / RecommendationEngine
        ↓
IncidentManager + robot failure/recovery handling
        ↓
EvidenceTimeline + EvidenceSynthesis + IncidentExplanation + ReliabilityMemory
        ↓
Genesis result / report / Field Agent session

Separate offline path: simulator → dataset/labels/features → model training/validation
~~~

### Proposed conceptual flow

~~~text
EXTERNAL SYSTEM
↓
INTERFACE / ADAPTER
↓
NORMALIZED OBSERVATIONS + source/time/units/limitations
↓
GENESIS CORE: history / quality mechanics / change / evidence / comparison / records
↓
EVIDENCE / ASSESSMENT / INCIDENT
↓
DOMAIN POLICY: signals, risk/state interpretation, diagnosis, permitted recommendations
↓
RECOMMENDATION → ACTION (recorded, not executed by core)
↓
OUTCOME (sourced, distinguished from inference) → MEMORY
~~~

### Differences today

Observations are robot-shaped before reaching Genesis. Feature building and robot-keyed history are inside the facade path. The DecisionPipeline invokes shared mechanics and robot policy directly. Simulator flags feed state/lifecycle; baseline asks for simulator health. RecommendationEngine is robot policy instantiated in Genesis. Outcome sources are mixed between recorded outcome, inferred state resolution and simulator events. Genesis facade initializes with prediction/diagnosis model unavailable by default, so the public path reports them unavailable unless explicitly supplied elsewhere.

## 6. Boundary test — exactly three domains

### Robotics
- **Interface provides:** source fields, robot identity, timestamps, units, metadata and limitations.
- **Domain defines:** robot/profile, canonical motor/battery/workload/state fields, quality groups, limits/signals, failure/recovery semantics, diagnosis/model schema, peer group and operator actions.
- **Core could consume:** ordered sourced observations, quality/evidence, pattern, comparison, lifecycle/action/outcome records.
- **Core should not know:** ROS keys, motor/battery limits, manufacturer/type cohorts, robot labels or safe robot actions.

### EV charging
- **Interface provides:** voltage/current/power, connector/charger temperature, session state, fault code, identity, timestamp, unit/source metadata.
- **Domain defines:** charger/connector/session semantics, operating envelopes, limits/signals, fault/derating states, diagnosis and safe actions.
- **Core could consume:** time-indexed observations, quality, changes, evidence, incidents, actions/outcomes and memory.
- **Core should not know:** fault-code meanings, OCPP/session policy, safe current limits or charger peer cohorts.

### Industrial pump
- **Interface provides:** vibration, pressure, flow, motor temperature, current, RPM, operating hours, fault codes, identity, time and units.
- **Domain defines:** operating regime, pressure/flow/RPM relationships, vibration signatures/limits, fault classes and shutdown/restart policy.
- **Core could consume:** sourced time series, quality, configured patterns, comparisons, lifecycle and confirmed outcomes.
- **Core should not know:** cavitation/bearing/seal semantics, pump operating envelopes, RPM-conditioned limits or safe shutdown rules.

These mappings are not adapter designs; each shows what the boundary must keep out of shared core.

## DO NOT DO YET

- Do not rewrite all robot_id references.
- Do not replace robot_id with asset_id or create universal Asset.
- Do not recast every sensor as a universal ontology.
- Do not move all modules into packages as a substitute for a contract.
- Do not create universal ML models or diagnosis labels.
- Do not build EV/pump/other industry adapters before a real use case.
- Do not remove robot-specific signals, profiles, recommendations or fleet rules.
- Do not redesign the whole pipeline.
- Do not treat missing failure_event as proof of healthy baseline.
- Do not change production behavior as part of boundary definition.

## Proposed evolution path

### Stage 1 — define baseline eligibility without changing behavior
Specify the explicit owner and conservative unavailable behavior for baseline qualification. No module move or output change.

### Stage 2 — isolate comparison mechanics from robot qualification
If real field baselines are needed, have the robotics side supply eligible records to the existing aggregation. Verify simulator truth is not required for deployable history.

### Stage 3 — add a second domain only for a real use case
Add its own interface and domain rules against the smallest proven observation/evidence boundary. Do not map its measurements into robot names.

### Stage 4 — test whether the boundary holds
Run both domains through common mechanisms and generalize only the parts proven common.

## Genesis Core Today

Genuinely reusable today: timestamp/sampling analysis, temporal arithmetic, quality-check patterns, evidence provenance/synthesis structures, event timeline, incident/action/outcome record mechanics, memory storage and report projection. Some are only conceptually reusable because inputs still depend on robot fields. There is no neutral end-to-end core API.

## Robotics Domain Today

Robot identity/profile, motor/battery/workload/state vocabulary, feature/diagnosis schemas, RF artifact, engineering limits, robot fleet grouping, failure/recovery interpretation and operator recommendations are robotics-specific. This is appropriate for the first domain.

## Interface Boundary Today

ROS2TelemetryAdapter maps ROS-like messages and units. GenesisFieldAgent records read-only robot sessions and may call Genesis. Normalizer handles aliases/units but also validates robot fields/states. Capability discovery inventories the robot catalog. This is not yet an interface for arbitrary domains.

## Biggest Architectural Problem

Domain policy and orchestration are interwoven, with a verified runtime baseline mismatch: baseline eligibility requires simulator health/failure fields absent from external streaming observations. Removing that filter without an explicit rule would silently treat unclassified history as healthy.

## First Boundary to Establish

An explicit baseline-eligibility policy between reusable metric aggregation and robotics-specific eligibility interpretation.

## Why This Boundary

It addresses a proven contract seam with minimal scope, preserves baseline meaning, and matters to field investigations: external records cannot pass the current health filter. It can be introduced without changing identity, features, models, state, fusion, thresholds or robot behavior. A neutral identity/observation model would be broader and premature with one implemented domain.

## What We Should Not Change Yet

- Do not rewrite robot_id or introduce Asset.
- Do not move/rename every module or redesign the pipeline.
- Do not create universal feature, diagnosis or ML schemas.
- Do not build unrelated industry adapters before a concrete use case.
- Do not remove robot-specific signals, recommendations, profiles or fleet semantics.
- Do not infer baseline health from absence of simulator flags.
- Do not change model, labels, thresholds or behavior in this document task.

## Next Engineering Task

Implement only the baseline eligibility seam: make eligibility explicit and supplied by Robotics, preserve current result shape and conservative unavailability for unqualified history, and add focused tests for unqualified external history, explicitly approved baseline records, and exclusion of degraded/simulator-only records. Keep model, labels, thresholds, fusion, recommendations and identity unchanged.
