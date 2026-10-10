# Genesis Core — Domain Independence Architecture Audit v0.1

**Scope:** Read-only architecture review. No production code, tests, behavior, models or configuration were changed. This assesses architecture only.

## Executive conclusion

**Architecture maturity: Partially reusable.** Genesis has useful reusable primitives for observation quality, temporal comparison, evidence provenance/synthesis, incident lifecycle, memory and sampling context. However, its public pipeline and data contracts are robotics-shaped end to end: the public facade requires robot identity, normalizes a fixed robot telemetry vocabulary, and creates robot reliability/fleet/recommendation components. Signal groups, patterns, features, diagnosis, peer grouping and actions also encode robotics assumptions. Another measurable system cannot currently use Genesis by supplying only a transport adapter.

The supported direction is evolutionary: robotics stays the proving ground; define explicit boundaries before extracting shared components; each domain supplies measurement, state, signal, model, peer-group, diagnosis and action semantics. Do not generalize robotics semantics themselves.

## 1. Major component classification

| Component | Classification | Why and code evidence | Future treatment |
|---|---|---|---|
| genesis.py — Genesis facade | ROBOTICS-SPECIFIC | Requires robot_id, tracks per-robot state/history, uses fixed robot telemetry fields and returns a robot object. genesis.py:18-31, 70-75, 188-230, 254-289 | Keep as robotics API. A future domain facade may translate into a shared observation contract; do not silently make robot_id mean arbitrary equipment. |
| decision_pipeline.py — DecisionPipeline | DOMAIN-ADAPTIVE, currently robot-coupled | Reusable orchestration, but coordinates robot fields, incidents and fleet context and consumes failure_event/recovery_event. decision_pipeline.py:43-82, 113-181, 203-256, 339-388 | Retain orchestration after explicit event/state contracts; supply policy through domain components. |
| reliability_state.py — ReliabilityState | DOMAIN-ADAPTIVE | Transition mechanism may transfer; HEALTHY/WATCH/WARNING/CRITICAL/FAILED/RECOVERING and failure/recovery semantics are not universal. reliability_state.py:1-42 | Reuse lifecycle concepts; declare domain state mappings and recovery semantics. |
| reliability_signal.py — ReliabilitySignal | ROBOTICS-SPECIFIC | Thresholds concern battery level/drop, motor temperature, thermal rise, voltage drop and battery current. reliability_signal.py:3-29, 35-173 | Keep robot limits here; other domains define their own observable signals and limits. |
| reliability_fusion.py — ReliabilityFusion | DOMAIN-ADAPTIVE | Separates engineering evidence, ML output, quality limits and final risk; current policy assumes robot signals, fixed risk bands and critical override. reliability_fusion.py:8-17, 19-99 | Shared only over explicit domain-labeled evidence and policy. |
| observation_quality.py — ObservationQuality | DOMAIN-ADAPTIVE | Missingness, warm-up, invalid values, static sensors, jumps and disagreement are reusable checks; groups and battery 0–100 bound are robot-specific. observation_quality.py:23-67, 84-117, 126-190 | Reuse check mechanics; domains declare groups, representation constraints and consistency rules. |
| feature_contract.py | ROBOTICS-SPECIFIC | Difference/rate/rolling-window math is generic; raw and deployable schemas specify robot thermal, battery, power, workload, manufacturer/type. feature_contract.py:8-73, 80-158, 230-305 | Reuse temporal math where useful. Keep model schemas domain- and version-specific. |
| telemetry_features.py — TelemetryFeatureBuilder | DOMAIN-ADAPTIVE | Per-entity history/build pattern generalizes; reads identity.robot_id and fixed robot telemetry. telemetry_features.py:9-55 | Reuse behind neutral identity and domain feature definitions. |
| telemetry_pattern_engine.py | DOMAIN-ADAPTIVE | Chronological evidence and deterministic pattern descriptions generalize; configured patterns are temperature/battery/workload-specific. telemetry_pattern_engine.py:20-45, 86-165, 215-368 | Keep provenance/detector interface; domains provide pattern semantics. |
| evidence_engine.py | DOMAIN-ADAPTIVE | Evidence collection and source attribution are reusable; fields and signal descriptions are robot-specific. evidence_engine.py:13-72 | Keep evidence mechanics; supply field vocabulary from domain. |
| evidence_synthesis.py — EvidenceSynthesis | DOMAIN-ADAPTIVE, reusable organization with fixed vocabulary | Separates observations, patterns, engineering, ML, fleet/history, unknowns, recommendation, action and outcome; derives fields from robot feature contract. evidence_synthesis.py:7-35, 95-153, 273-370, 417-577 | Strong shared-core candidate: consume generic evidence records, retain domain wording at producers. |
| evidence_timeline.py | DOMAIN-ADAPTIVE | Ordered events generalize; methods include fused reliability, robot failure/recovery, diagnosis and recommendation. evidence_timeline.py:1-26, 41-203 | Keep timestamp/provenance timeline; allow domain event types. |
| incident_explanation.py | DOMAIN-ADAPTIVE | Evidence/lifecycle/memory explanation structure transfers; robot identity and fleet keys do not. incident_explanation.py:19-159 | Shared report projection over domain identity/evidence. |
| investigation_report.py | DOMAIN-ADAPTIVE | Deterministic projection does not infer; headings and temperature trajectory are robot-shaped. investigation_report.py:17-50, 117-144, 153-191, 247-267 | Retain projection pattern; domain-specific presentation at edge. |
| incident.py — Incident | DOMAIN-ADAPTIVE | Observations/evidence/predictions/diagnosis/recommendation/action/outcome/status are reusable; identity uses robot_id/site_id and time_step. incident.py:1-45, 47-135 | Retain lifecycle record; neutral subject identity only if needed by a second domain. |
| incident_manager.py | DOMAIN-ADAPTIVE | Create/update/fail/recover/close ownership transfers; active incident selection is by robot_id. incident_manager.py:4-20, 43-95 | Keep lifecycle ownership; delegate identity and domain transitions. |
| reliability_memory.py | DOMAIN-ADAPTIVE | JSON-safe storage and sanitization generalize; similarity uses robot/manufacturer/type, signals, diagnosis and state. Simulator truth is filtered. reliability_memory.py:8-29, 53-91, 221-294 | Keep store; make retrieval keys explicit and domain-specific. |
| fleet_baseline.py | ROBOTICS-SPECIFIC | Cohorts are robot_type and optional manufacturer; metrics are robot telemetry. fleet_baseline.py:21-31, 46-58, 77-134, 135-160 | Keep robot fleet rules. Other domains define peer cohorts and metrics. |
| comparison_engine.py | DOMAIN-ADAPTIVE | Historical numeric comparison is reusable, but only motor temperature and thermal rise are compared. comparison_engine.py:1-64 | Generalize around declared metrics only when justified by another use case. |
| baseline_engine.py | ROBOTICS-/SIMULATOR-SPECIFIC | Eligibility requires health == healthy, robot_state != failed and excludes failure_event; outputs motor temp, thermal rise, battery. baseline_engine.py:1-61. Streaming builder does not supply health: telemetry_features.py:15-52. | Keep aggregation concept; use observable/domain-approved baseline eligibility, not simulator truth or absent health. |
| recommendation_engine.py | ROBOTICS-SPECIFIC | Recommendations refer to robot operation, workload, thermal system, battery and power. recommendation_engine.py:17-50, 56-75, 77-149 | Preserve single recommendation owner; actions/wording come from domain policy. |
| prediction_engine.py | DOMAIN-ADAPTIVE | Ordered schema enforcement/model wrapper generalize; current artifact expects robot DEPLOYABLE_FEATURES. prediction_engine.py:2-23, 25-63 | Bind artifact to domain, target, feature schema and version. Wrapper reuse is not model transfer. |
| diagnosis_engine.py | ROBOTICS-SPECIFIC | Model distinguishes thermal vs battery; evidence and causes encode motor, battery, thermal rise and workload. diagnosis_engine.py:1-67, 69-222, 228-313 | Keep diagnosis in robot domain; other domains need separate targets, evidence rules and validation. |
| normalizer.py | DOMAIN-ADAPTIVE | Alias/unit conversion is reusable; aliases, required fields and working/idle states are robot-specific. normalizer.py:3-48, 61-79, 81-160 | Source translation at interface; domain declares canonical fields/states. |
| history.py | DOMAIN-ADAPTIVE | Ordered in-memory records/events/incidents are general; get_robot_incidents is robot-specific. history.py:1-44 | Reuse behind neutral identity/persistence boundaries. No durable multi-process persistence. |
| robot_profile.py and robot.py | ROBOTICS-SPECIFIC | Robot identity and working/idle temperature/thermal-rise limits, battery and motor temperature. robot_profile.py:1-29; robot.py:1-34 | Keep in robotics domain. |
| robot_adapter.py | ROBOTICS-SPECIFIC | Adapter concept transfers; actual base/simulated adapter is robot-record based. robot_adapter.py:8-25 | Keep robot adapters at robot boundary. |
| ros2_telemetry_adapter.py | ROBOTICS-SPECIFIC | Maps ROS-like diagnostics and units into the robot schema; explicitly read-only with no ROS import/control. ros2_telemetry_adapter.py:1-5, 17-54, 89-127, 129-180 | Keep as edge integration; other transport adapters translate without inference. |
| telemetry_capability_discovery.py | DOMAIN-ADAPTIVE | Coverage/validity inventory generalizes; field catalog/capability names are thermal, battery and workload. telemetry_capability_discovery.py:12-57, 100-180 | Reuse discovery pattern; domain supplies catalog and capabilities. |
| telemetry_sampling_context.py | DOMAIN-INDEPENDENT | Describes observed intervals against optional cadence and does not claim a gap without context. telemetry_sampling_context.py:12-34, 38-124 | Strong shared-core candidate; normalize time at interface. |
| genesis_field_agent.py, config and session schema | ROBOTICS-SPECIFIC | Robot diagnostics/session identity and robot_id config/schema; optional pass-through to Genesis. genesis_field_agent.py:16-73; genesis_field_agent_config.py:10-38; genesis_field_session_schema.json:1-35 | Keep read-only robotics integration. Other domains need separate adapters. |
| feature_engineering.py, train_model.py, label_generator.py, fleet_simulator.py | SIMULATOR-SPECIFIC development path | Generate synthetic robot trajectories, event/horizon labels and fit RF models offline. Labels/hidden state are not universal targets. label_generator.py:1-81; train_model.py:1-95; feature_contract.py:8-73 | Keep offline and separated; each target/schema/artifact is domain/version-specific. |
| validation_experiment.py, validation_factorial.py, failure_investigation.py, inspect scripts | SIMULATOR-SPECIFIC | Evaluate simulated scenarios, not runtime inference. Catalogued as offline in architecture docs/contract. | Keep outside runtime; report evidence as simulator-specific. |
| pattern_detector.py | DOMAIN-ADAPTIVE | Incident/diagnosis recurrence concept transfers; categories are current Genesis diagnosis/incident vocabulary. Distinct from telemetry trajectory engine. | Keep separate meanings; configure categories by domain. |
| architecture_contract.py and test_architecture_contract.py | DOMAIN-INDEPENDENT metadata; UNCERTAIN as enforcement | Registry describes layers/owners/forbidden capabilities; tests assert registry entries, not Python import graph. architecture_contract.py:1-5, 15-77, 80-122; test_architecture_contract.py:1-76 | Treat as descriptive design metadata, not enforced package isolation. |
| analyzer.py, main.py, demos and CLI | UNCERTAIN / legacy or interface-specific | Legacy, demo and offline entry points coexist with public facade; not the stable shared reasoning boundary. GENESIS_ARCHITECTURE_V0_1.md: system flow / known debt | Keep isolated and identify public API vs development entry points. |

## 2. Hidden robotics coupling and architectural risks

| Coupling | Current form | Assessment |
|---|---|---|
| Identity/grouping | Genesis, feature history, incidents and memory use robot_id; manufacturer/type define fleet peers. | Appropriate in robot adapter; accidental core coupling in reusable lifecycle/evidence orchestration. A charger/pump needs asset/component identity and hierarchy. |
| Measurements/features | Motor/ambient temperature, battery, voltage drop, workload, robot state and fixed allowlists recur throughout. | Appropriate robotics behavior; risky only if treated as universal. Reused temporal math does not make measurements equivalent. |
| Lifecycle events | Pipeline reads failure_event/recovery_event, passes actual_failure into state, marks incident failed and copies simulator failure type/state into outcome. | Simulator convention leaks into runtime. Feature builder supplies None for external telemetry, so dormant there, but pipeline still depends on convention. Eventual runtime should receive sourced domain events/outcomes explicitly. |
| State vocabulary | HEALTHY/WATCH/WARNING/CRITICAL/FAILED/RECOVERING. | Domain-adaptive but currently robot-shaped; charger derating or pump shutdown may not equal robot failed/recovering. |
| Limits/recommendations | Fixed robot thermal/battery/voltage limits and robot workload/inspection actions. | Correct for robot rules; unsafe to transplant. |
| ML/diagnosis | Robot feature allowlist, future failure labels, thermal/battery classes. | Wrapper reusable, model semantics not. Independently define and validate each target/schema. |
| Fleet | Manufacturer/type cohort and robot telemetry. | One domain's peer policy, not universal cohorting. |
| Baseline eligibility | Runtime baseline requires simulator health and excludes failure_event, while streaming records omit health. | Concrete runtime/data-contract mismatch: ordinary deployable telemetry cannot establish this baseline eligibility. |
| Interfaces | ROS keys, robot aliases, temperature units and working/idle state. | Appropriate at robotics edge; normalization must not infer health or cause. |
| Boundary enforcement | Root-level modules and descriptive layer registry. | Architectural risk: declared intent does not prevent forbidden imports/dependencies. |

Specific evidence:
- Genesis._normalize_record requires robot_id and recognizes robot state/type/manufacturer and a fixed telemetry set (genesis.py:188-230).
- TelemetryFeatureBuilder isolates history per robot_id, but its identity/input schema does not transfer unchanged (telemetry_features.py:9-55).
- feature_contract.py is an authoritative, leakage-conscious schema for the current robot models, not universal features; it lists simulator-only fields (feature_contract.py:8-73, 80-158).
- ObservationQuality uses reusable checks but hard-codes thermal/battery/workload groups and battery-level bounds (observation_quality.py:23-67, 126-163).
- TelemetryPatternEngine maintains evidence discipline but supports temperature/battery/workload patterns (telemetry_pattern_engine.py:20-45).
- EvidenceSynthesis imports robot RAW_FEATURES/DEPLOYABLE_FEATURES to determine observation/temporal fields (evidence_synthesis.py:7-35).
- ReliabilityMemory filters simulator truth, which is a good boundary, but similarity uses robot identity and domain diagnoses/signals (reliability_memory.py:8-29, 221-294).
- Architecture metadata tests assert declarations rather than import boundaries. Documentation says field-test infrastructure is unimplemented, while this checkout contains genesis_field_agent.py, config and schema; docs/registry have drifted from implementation.

## 3. The actual Genesis Core primitives

The proposed sequence is **partly supported conceptually**, not implemented as a domain-independent system.

| Primitive | Present implementation | Assessment |
|---|---|---|
| OBSERVE | Genesis, normalizer, telemetry/ROS adapters, feature builder and history | Present; contract assumes robot identity, fields and time-step conventions. |
| REPRESENT STATE | Canonical telemetry/features, ReliabilityState and robot_state | Mixed: observation representation is robot-specific; lifecycle labels are policy vocabulary, not neutral physical state. |
| DETECT CHANGE | Shared deltas/rates/windows, pattern engine, history/baseline comparisons | Present; temporal math generalizes, metrics do not. |
| IDENTIFY PATTERNS | TelemetryPatternEngine and pattern_detector.py | Distinct meanings: measured trajectory vs event/diagnosis recurrence. Both domain-tuned. |
| COMPARE | ComparisonEngine, BaselineEngine, FleetBaseline, memory matching | Present but distinct definitions of normal/peer/similar, with robot and simulator dependencies. |
| ASSESS RISK | ReliabilitySignal, optional PredictionEngine, ReliabilityFusion, ReliabilityState | Present; robot-specific semantics. Pattern analysis itself does not set risk. |
| SYNTHESIZE EVIDENCE | EvidenceEngine, EvidenceSynthesis, IncidentExplanation, EvidenceTimeline | Strong reusable provenance concepts; public shapes still expose robot fields. |
| EXPLAIN | IncidentExplanation and investigation_report.py | Present as projection; wording is domain-dependent. |
| RECOMMEND | RecommendationEngine | Present, explicitly robot-operation policy. |
| OBSERVE ACTION | Incident action methods and explanation | Record structure exists; Field Agent/ROS path is read-only and does not execute actions. |
| OBSERVE OUTCOME | Incident outcome/close, timeline, pipeline recovery resolution | Present, but recorded outcomes, inferred resolution and simulator events are mixed. |
| REMEMBER | ReliabilityMemory and History | Present, deterministic/in-memory; incident-centric and robot-specific retrieval, not durable multi-process storage. |

**Existing:** provenance-bearing evidence; event/timeline ordering; JSON-safe memory sanitization; availability/consistency checks; temporal windows; timestamp analysis; action/outcome records.

**Missing:** neutral subject/observation/evidence/event contracts; domain-declared units/quality semantics; explicit outcome source contract; model metadata binding domain/target/schema; enforced dependencies.

**Duplicated:** historical temperature comparison, healthy baseline, peer statistics and incident matching each have distinct definitions of reference/normal/similar.

**Mixed:** DecisionPipeline reads simulator truth while coordinating runtime; BaselineEngine is runtime-called but requires simulator health; Genesis handles facade plus robot parsing; feature records mix identity/time, telemetry, derived values and simulator placeholders.

**Terminology collision:** “pattern” means telemetry trajectory or incident/diagnosis recurrence. “Baseline” means healthy-history summary or peer statistics.

## 4. Proposed conceptual architecture (not implemented)

This flow is supported only as shared orchestration/evidence conventions around domain-supplied reasoning, not a universal feature set or model.

~~~text
GENESIS CORE
Observation → State/History → Change Detection → Pattern Analysis
            → Baseline/Comparison → Risk/Inference → Evidence Synthesis
            → Explanation → Recommendation lifecycle → Action record
            → Outcome record → Memory
                 ↑                         ↑
              domain contract and sourced evidence/events

ROBOTICS DOMAIN PACKAGE           OTHER DOMAIN PACKAGE
robot identity + ROS fields       asset identity + domain fields
robot signals/state/diagnosis     charger/pump/DC signals/state/diagnosis
robot model/actions               domain model/actions
                 ↑
INTERFACE / ADAPTERS
ROS 2, robot logs, EV API, PLC/OPC-UA, CSV, MQTT, other transport
~~~

### Core layer
Preserve ordered observations, time, source and provenance; apply declared quality checks; calculate temporal operations with declared semantics/history; store evidence/events; preserve observation → pattern/evidence → inference → recommendation → action → outcome; support generic lifecycle and memory without prescribing failure/recovery; compare declared metrics without implicit universal “healthy” or peer rules.

### Domain layer
Supply subject identity/hierarchy and cohorts; measurements, units, bounds, derived features, history needs and quality groups; engineering limits, state mapping, diagnosis and target labels; model schema/artifact; allowed recommendations/actions; meaning of failure/recovery, normal regimes and baseline eligibility.

### Interface layer
ROS 2 and robot logs remain robotics adapters. Charger APIs, PLC/OPC-UA, CSV and MQTT need source parsing and mapping for identity/time/measurements/units/limitations. Adapters must not invent evidence or conclusions. Normalization translates syntax/units; domain modeling gives values meaning.

## 5. Mapping to exactly three domains

### A. EV charging station
- **Reusable:** ordered observations, quality, sampling, temporal patterns, history/baseline, evidence provenance, incident/action/outcome, memory and report.
- **Domain-specific:** charger/connector/contactor, model/firmware, charging session, energy/current/voltage semantics, fault codes, safe derating/stop policy and diagnosis labels.
- **Adapters:** charger API/logs, OCPP/MQTT where used, site/charger identity, timestamp and units. Current ROS adapter only emits robot schema.
- **New signals:** connector-vs-cabinet temperature disagreement; current/voltage/power envelope; session interruptions/retries; energy-delivery deviation; fault-code evidence. Limits are charger-specific.
- **Breaks today:** robot identity/type/manufacturer grouping, motor/ambient/thermal-rise and battery feature contract, robot-workload recommendations. Charger energy/storage is not automatically robot battery semantics.
- **Can current core work without rewriting?** Evidence/history/lifecycle concepts can be reused; current API cannot represent a charger natively without misusing robot fields or supplying charger domain semantics and adapters.

### B. Industrial pump
- **Reusable:** observation history/quality/sampling, change/persistence, evidence synthesis, peer/history comparison, lifecycle and outcome recording.
- **Domain-specific:** pump/motor/drive identity, operating point, RPM, pressure, flow, vibration spectrum, bearing/seal/impeller labels, hours and shutdown/restart policy.
- **Adapters:** PLC/OPC-UA, historian/CSV or MQTT for time, units, hierarchy and mode.
- **New signals:** vibration-band changes; pressure/flow residuals; RPM-normalized vibration; cavitation-like operating signatures; current vs load. These are evidence, not causes.
- **Breaks today:** battery/thermal/workload feature set, working/idle state, robot diagnosis/action language and cohorts that ignore operating point/duty.
- **Can current core work without rewriting?** Orchestration/evidence concepts yes; current policy/features are not pump-ready. Pump-specific modeling and signals are required.

### C. Data center infrastructure
- **Reusable:** time-series quality/sampling, change detection, baselines, evidence timeline, incidents, action/outcome and memory.
- **Domain-specific:** rack/host/fan/PSU/CRAC hierarchy, service role, CPU/GPU/rack temperature, fan speed, cooling load, power, network/hardware errors and service impact.
- **Adapters:** metrics APIs, SNMP, BMC/IPMI/Redfish, logs, CSV or MQTT with hierarchy/time/units.
- **New signals:** temperature conditioned on utilization/ambient; fan command-speed disagreement; sensor disagreement; cooling/power behavior; error bursts and correlated rack events.
- **Breaks today:** one robot per entity, motor/battery vocabulary, manufacturer/type peers, robot target/features/actions. A data-center event may span devices unlike current per-robot incident ownership.
- **Can current core work without rewriting?** Evidence/time-series concepts transfer; identity, peer, feature and cross-device incident assumptions need domain/hierarchy policy.

## 6. Risks and concepts that should not be generalized

1. Do not over-generalize before a second concrete domain exists; one domain does not justify speculative plugin registries/schema DSLs.
2. Do not call robot measurements universal features. Sensor location, operating regime, meaning, bounds and missingness differ; bind models to target/domain version.
3. Do not make fleet universal. The reusable idea is a declared peer cohort; a robot fleet is one cohort policy.
4. Do not universalize labels or diagnosis. Current risk target is a future-horizon robot failure label and diagnosis is thermal vs battery; each domain needs independent outcomes/validation.
5. Do not move action policy into generic core. Recommendation lifecycle is reusable; “reduce robot workload” is not.
6. Generic names do not prove neutrality: baseline, quality, synthesis and incident manager still contain health/battery/robot assumptions.
7. Do not let simulator concepts define runtime truth. failure_event, recovery_event and health are simulator/outcome conventions; use explicit, sourced domain events eventually.
8. Do not confuse normalization with domain modeling. Alias/unit conversion must not decide diagnosis, baseline health or cause.
9. Do not force every domain into one lifecycle: derating, maintenance, service incidents, multi-asset propagation and component replacement differ.
10. Keep robotics-specific concepts at the robotics boundary: ROS 2, profiles, telemetry mappings, fleet cohorts, motor/battery limits, robot diagnosis and robot actions.

## 7. Recommended architectural principles

1. Keep shared core focused on ordered observations, evidence provenance, lifecycle records and outcomes; keep robot semantics at the robotics boundary.
2. Treat feature_contract.py as the current robot model contract, not universal features. Bind each future artifact to domain, target, schema and training/evaluation context.
3. Preserve observation, pattern, inference, recommendation, action and outcome distinctions; pattern, peer deviation and memory match are not cause or confirmed failure.
4. Adapters translate source format, units, timestamps and identity; they do not invent measurements or evidence.
5. Let each domain declare metrics, units, quality groups, operating context, state mapping, peer definition and limits.
6. Preserve recommendation ownership; source rules and allowed actions from the active domain.
7. Keep memory storage reusable and similarity keys domain-specific and inspectable.
8. Keep simulator labels/hidden state out of inference and runtime baseline eligibility.
9. Enforce dependency direction when package boundaries are real; current metadata is descriptive.
10. Keep robotics as first domain/proving ground; wait for a concrete second-domain use case before broad plugin abstractions.

## What Genesis is architecturally today

A robotics reliability intelligence pipeline with reusable evidence/time-series primitives. It has a public investigation facade, coordinated decision pipeline, separated observation/pattern/engineering/ML evidence, incident/action/outcome records, memory and source adapters. Data contracts and operational policy remain robotics-specific.

## What Genesis could become

A domain-adaptive reliability/change-intelligence system sharing observation ordering, evidence provenance, temporal reasoning, lifecycle and memory, with explicit domain contracts for measurements, state, cohorts, signals, models, diagnosis and actions.

## What prevents that today

No neutral subject/observation/evidence/event contract at the public boundary; robot-shaped features and quality groups; direct simulator-event conventions in the pipeline; runtime baseline requiring simulator health; robot-specific recommendations/diagnosis; and descriptive rather than enforced module boundaries.

## What should be changed eventually

Only when a concrete second domain is in view: define the smallest shared observation/evidence/event/domain-policy contracts that use case needs; move robot mappings/signals/diagnosis/model/actions behind a robotics boundary incrementally; route simulator outcomes through an explicit offline/event boundary; enforce dependency direction. Keep today's robotics path as compatibility/proving ground.

## What should NOT be changed yet

Do not rewrite the pipeline, rename modules, replace robot features/models/thresholds, build a generic plugin framework, claim robot fleets are universal peers, or move robotics thresholds/recommendations into universal core rules. The code does not yet establish that those abstractions are needed.
