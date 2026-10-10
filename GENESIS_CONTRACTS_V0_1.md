# Genesis Contracts v0.1

These are logical contracts for the current implementation, not new wire schemas. Exact public return fields remain those of the current functions/classes.

## Data contract

**Observation input:** adapter/raw telemetry may use source-specific names. Normalization and adapters translate it into Genesis records carrying robot identity, observation time/step, and available telemetry values. Keep identity (`robot_id`, manufacturer/type/site where available), timestamp/order, and measurements explicit. Unknown or absent measurements remain unavailable; do not invent sensor values.

**Canonical/derived record:** `feature_contract.py` is authoritative for deployable risk/diagnosis features. `TelemetryFeatureBuilder` preserves per-robot temporal history and applies the same definitions used by offline feature engineering. Temporal features are unavailable during required warm-up. Simulator-only truth/labels are not model inputs.

**Offline labels:** labels carry target eligibility and horizon semantics produced by `label_generator.py`; incomplete horizons remain unknown. Simulator event fields are evaluation ground truth and must not leak into inference.

## Analysis contracts

- Observation quality answers whether evidence is available/trustworthy; it is not failure prediction.
- Telemetry pattern analysis consumes chronological observable telemetry/derived records and returns deterministic pattern names, supporting observations/metrics, status, and limitations. It emits no probability, diagnosis, cause, recommendation, or state transition.
- Engineering signal analysis returns threshold-based signal evidence under existing configured rules.
- Prediction and diagnosis wrappers prepare columns in their trained feature schema and return model inference availability/results. They do not own operational state.
- Fleet baseline compares compatible observable peer snapshots and returns context plus limitations; it cannot claim causality or set state.
- Historical comparison and memory return prior context, not proof of the current event.

## Evidence contract

Evidence is provenance-bearing and source-separated. Conceptual kinds include `OBSERVATION`, `PATTERN`, `ENGINEERING_SIGNAL`, `ML_INFERENCE`, `FLEET_COMPARISON`, and `HISTORICAL_COMPARISON`. A record may carry a stable evidence identifier/type, source, statement, availability, supporting data, and limitations. A pattern statement describes measured behavior; downstream inference remains separately attributed. Synthesis preserves source evidence and limitations and does not alter model outputs, state, or lifecycle.

## Incident contract

`Incident` stores observations, evidence, predictions, optional diagnosis/confidence, recommendations, actions, outcome, and status. `IncidentManager` owns creation/update/failure/recovery/close lifecycle operations. Human action and outcome are recorded only when provided; pending or absent values remain pending/unavailable. Evidence producers must not create or close incidents themselves.

## Decision contract

`DecisionPipeline` coordinates existing signal, model, quality, context, fusion/state, recommendation, and lifecycle components. `ReliabilityFusion` and `ReliabilityState` retain their existing responsibilities for combining evidence and representing/transiting state. `RecommendationEngine` owns recommendation rules. A telemetry pattern, fleet outlier, memory match, or missing observation alone does not independently establish a cause or physical failure.

## Memory contract

`ReliabilityMemory` stores and retrieves compact structured incident knowledge. It excludes known simulator-only truth keys when cleaning values. It is contextual input for later synthesis; it does not own current reliability state, lifecycle, or recommendations.

## Interface contract

- `Genesis.investigate(...)` is the public application entry point for supported telemetry input shapes and returns a JSON-compatible structured investigation.
- `genesis_cli.py` presents the complete structured result as JSON or a concise operator view. It may format/filter for display but must not create a second inference or decision path.
- `ros2_telemetry_adapter.py` translates a ROS-like source payload into Genesis observation data. It does not send commands or control the robot.
- `main.py` is a development/demo pipeline runner, not the public product API or an independent policy engine.
- Field-test modules are not present. If implemented, they should capture session/run/configuration/observation/report data and invoke the existing Genesis interface; they must not duplicate feature or reliability reasoning.

## Dependency direction

The permitted conceptual direction is:

```text
ingestion → normalization/contracts → analysis/context → decision orchestration
          → lifecycle/evidence/memory as coordinated outputs → public interface
```

Evidence producers may be invoked by orchestration and their results consumed by synthesis. They must not import lifecycle ownership to take lifecycle actions. `TelemetryPatternEngine` and `EvidenceSynthesis` do not depend on `IncidentManager`; `FleetBaseline` does not depend on state transitions; `ReliabilityMemory` does not depend on recommendations; the CLI consumes Genesis results; adapters do not depend on decision/policy components. Offline training/validation may consume the shared feature contract, but runtime inference must not consume labels or simulator-only truth.

`architecture_contract.py` is a lightweight descriptive registry, not an import graph validator. The layer registry records current files only; planned field-test boundaries are marked `NOT_IMPLEMENTED` separately.

