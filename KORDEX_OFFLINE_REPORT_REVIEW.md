# KORDEX offline report review

The offline telemetry report includes a descriptive review of the mapped recorded values: per-signal completeness, numeric range and simple summary statistics, robot-state counts, and timestamp interval summaries.

## Interpretation boundary

This is a descriptive layer, not a failure classifier. It does not apply engineering thresholds, infer physical causes, or validate failure-prediction accuracy. A change, missing value, or extreme value is a lead for an engineer to review—not proof of failure.

## Suggested engineering review

1. Confirm asset identity, channel meaning, calibration, and units against source documentation.
2. Compare values with manufacturer limits and the asset's operating envelope.
3. Check operating mode, workload, ambient conditions, and maintenance history for context.
4. Obtain independent inspection or corroborating evidence before recording a failure or cause.

The report is based only on the user-provided recorded file and mapped fields. It does not authenticate the physical source or sensor calibration.
