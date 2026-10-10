# Genesis Core Architecture v0.1

Status: **CURRENT architecture description**, with future boundaries labeled separately. This document describes the checked-in Python system; it does not assert production certification or real-robot deployment readiness.

## System flow

```text
robot / simulator / ROS 2 message
  → adapter and normalization
  → canonical telemetry + per-robot history + shared feature contract
  → observation quality and analysis sources
  → DecisionPipeline orchestration
       ├─ reliability fusion/state and recommendation
       ├─ IncidentManager lifecycle
       └─ evidence synthesis / timeline / memory context
  → Genesis public investigation result
       ├─ JSON/debug representation
       └─ human-readable CLI presentation
```

The offline development path is separate:

```text
FleetSimulator → dataset/labels → FeatureEngineer/shared feature contract
  → train_model → fitted model artifact → PredictionEngine at inference
  → validation experiments (offline only)
```

## Layers and boundaries

| Layer | Purpose and current components | Inputs → outputs | Allowed responsibility | Not allowed / dependency direction |
|---|---|---|---|---|
| Data ingestion | `robot_adapter.py`, `ros2_telemetry_adapter.py`, `history.py` | Adapter-specific records → telemetry snapshots/history | Read or translate incoming data; retain chronological observations | No model policy, reliability decisions, or robot control. Depends downward on data contracts. |
| Normalization and feature contract | `normalizer.py`, `telemetry.py`, `feature_contract.py`, `telemetry_features.py` | Raw values/history → canonical telemetry and deployable features | Normalize units/fields; compute shared features and warm-up availability | No failure inference or lifecycle. Feature contract is the shared offline/online definition. |
| Robot identity/profile | `robot.py`, `robot_profile.py` | Identity/profile values → robot identity and operating context | Hold robot metadata/profile thresholds | Does not decide fleet reliability. |
| Analysis/evidence producers | `observation_quality.py`, `telemetry_pattern_engine.py`, `reliability_signal.py`, `prediction_engine.py`, `diagnosis_engine.py`, `risk_engine.py` | Current record/history → quality, patterns, engineering signals, model inference | Produce bounded evidence/inference outputs under their existing contracts | No incident ownership. Pattern descriptions do not claim cause, diagnosis, risk score, or recommendation. |
| Context and historical comparison | `fleet_baseline.py`, `comparison_engine.py`, `baseline_engine.py`, `pattern_detector.py` | Current/peer/history records → fleet and recurrence context | Describe peer deviation or prior-event similarity | Fleet context does not set reliability state. `pattern_detector.py` is event/diagnosis recurrence analysis, distinct from telemetry pattern analysis. |
| Reliability memory | `reliability_memory.py` | Structured incident/explanation → stored and retrieved historical context | Persist/query incident knowledge and sanitize simulator-only fields | Does not infer current state or generate recommendations. |
| Evidence | `evidence_synthesis.py`, `evidence_engine.py`, `evidence_timeline.py`, `incident_explanation.py` | Observation and source outputs → structured evidence, timeline, explanation | Preserve provenance, limitations, and source separation | Synthesis/explanation do not own lifecycle or reliability-state policy. |
| Incident lifecycle | `incident.py`, `incident_manager.py`, `reliability_event.py` | Pipeline events and evidence → incident state/history | Create, update, fail, recover, and close incident records | `IncidentManager` owns lifecycle transitions; producers do not directly own lifecycle. |
| Decision and orchestration | `decision_pipeline.py`, `reliability_fusion.py`, `reliability_state.py`, `recommendation_engine.py`, `warning_engine.py` | Evidence/inference → fused state, transition, warning/recommendation and coordinated result | Existing rules, thresholds, state transitions, and pipeline sequencing | Pattern evidence cannot override model/engineering/fusion. Recommendation ownership stays in `RecommendationEngine`. |
| Interface/platform | `genesis.py`, `genesis_cli.py`, `demo_genesis_investigation.py`, `main.py` | User/API input or demo invocation → complete structured result/rendering | Genesis validates/coordinates public investigations; CLI formats returned data; `main.py` runs development pipeline | CLI is presentation only. `main.py` is a development/demo entry point, not a second policy owner. |
| Offline training/validation | `fleet_simulator.py`, `dataset_generator.py`, `label_generator.py`, `feature_engineering.py`, `train_model.py`, `validation_experiment.py`, `validation_factorial.py`, inspection scripts | Simulated/raw datasets → eligible labels, features, artifacts, experiments | Dataset creation, training, and offline evaluation | Offline simulator truth/labels must not become deployable inference inputs. No runtime decisions. |
| Legacy analysis | `analyzer.py` | History/profile → rule-based console analysis | Retain legacy/demo rule analysis | Not the current Genesis reliability pipeline. |

## Public and adapter boundaries

- **Public API:** `Genesis.investigate(...)` is the application-facing entry point. It accepts supported telemetry shapes, normalizes/validates them through current helpers, coordinates the pipeline, and returns a JSON-compatible structured investigation.
- **Adapter boundary:** adapters translate source-specific payloads into Genesis telemetry. `ROS2TelemetryAdapter` is ROS-free and translates duck-typed diagnostic messages. It is ingestion only; it cannot command a robot.
- **CLI boundary:** `genesis_cli.py` obtains a result and renders either concise operator text or complete JSON. It must not compute reliability outcomes independently.
- **Offline boundary:** simulator, labels, training, and validation are development tools. The model's inference schema is constrained by `feature_contract.py` and model feature order.

## Safety and evidence discipline

Genesis distinguishes observation, deterministic pattern description, engineering signal, ML inference, decision/recommendation, human action, and outcome. A pattern is not a diagnosis or cause. Fleet comparison and historical memory are context, not proof. Missing or degraded observation quality limits what can be inferred; lack of an observed signal is not automatically evidence of health. Only existing decision/state components own operational state and lifecycle policy.

## Future boundaries (not implemented here)

Field-test session/configuration/runner/report modules are **not present in this checkout**. If introduced, they belong to field-test data infrastructure: capture session configuration, robot/site identity, raw/normalized observations, run metadata, and reports. They should call Genesis through its public interface and must not duplicate feature, risk, fusion, diagnosis, recommendation, or lifecycle reasoning. Hardware control, deployment orchestration, durable production storage, authentication, and a production transport service are also outside this v0.1 architecture description unless implemented separately.

## Known architecture debt

- The repository contains both current pipeline modules and legacy/demo/offline code at its root, so boundaries are logical rather than enforced by packages.
- `main.py` and validation scripts combine orchestration and reporting for experiments; keep this isolated from production policy ownership.
- Adapter-specific schemas and normalizer input expectations are not yet one versioned transport schema.
- In-memory `History` and `ReliabilityMemory` do not provide durable multi-process storage.
- The architecture contract is descriptive metadata; it is not a static import/dependency checker.


## Security / Trust Boundary v0.1

Genesis now treats observation security as a distinct architectural concern alongside observation quality. The `observation_security.py` component assesses source identity/provenance, authentication status, authorization status, integrity status, and freshness. Unknown properties remain explicitly unknown; they are not treated as trusted by default.

Security assessment is descriptive in v0.1. It is exposed to evidence synthesis and the public investigation result, but it does not silently alter inference thresholds, reliability-state transitions, or operational recommendations.

Production security capabilities such as cryptographic message integrity, device authentication, authorization infrastructure, secure transport, durable audit logging, and distributed replay protection remain future boundaries.
