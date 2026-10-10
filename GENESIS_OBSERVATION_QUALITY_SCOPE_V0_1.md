# GENESIS Observation Quality Scope v0.1

## Purpose

Observation quality must be scoped to the evidence it actually affects.
A degraded signal group must not contaminate unrelated evidence groups merely because the overall observation-quality status is degraded.

## Problem Found

The abrupt-change quality check was evaluated across all telemetry fields while running once for each signal group. Consequently, a bad `battery_level` could be recorded as an abrupt-change issue in the thermal and workload groups.

This caused unrelated evidence to appear degraded.

## Fix

The abrupt-change check now receives the fields belonging to the current signal group and evaluates only those fields.

Observation Quality also exposes `field_groups`, mapping each feature to its relevant signal group(s) and scoped quality status.

Example:

```text
battery_level = invalid

Overall quality: DEGRADED

battery group:
  DEGRADED

thermal group:
  AVAILABLE

motor_temperature:
  AVAILABLE

battery_level:
  DEGRADED
```

## Evidence Propagation

Telemetry evidence now carries:

- `quality_scope`
- `quality_status`
- `usable`

This preserves the distinction between:

> overall data quality is degraded

and:

> this particular observation is unusable.

## Important Boundary

This change does **not** claim that a partially degraded record is safe for the global ML model. `prediction_ready` remains a separate global contract based on the model's required feature set and history.

The purpose is evidence-level scoping, not automatic model approval.

## Validation

Focused Observation Quality tests: 17 passed.

Full Genesis regression: 440 tests passed.

## Engineering Lesson

Quality must propagate according to dependency, not according to a global status flag.

A failure in one evidence path should affect only the conclusions that depend on that path.
