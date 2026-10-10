# Genesis Measurement Disagreement Stress Test v0.1

## Purpose

Stress-test whether Genesis can distinguish disagreement in measurements from evidence of physical asset failure.

This is an architectural experiment, not a production sensor-redundancy subsystem.

## Core question

When two measurements disagree, can Genesis avoid:

1. declaring one sensor wrong without evidence;
2. selecting the larger value as truth;
3. treating every disagreement as an asset failure;
4. treating different physical locations as contradictory evidence;
5. treating stale or invalid measurements as equally trustworthy?

## Expected reasoning

```text
Measurements
    ↓
Semantic validity
    ↓
Measurement validity / calibration
    ↓
Freshness / temporal compatibility
    ↓
Physical context compatibility
    ↓
Agreement or disagreement
    ↓
Evidence interpretation
```

A material disagreement between two current, valid, calibrated measurements of the same physical quantity and location should become an **investigation signal**, not an automatic diagnosis.

## Cases

- Agreement
- Small disagreement
- Strong disagreement
- Stale measurement
- Invalid measurement
- Different physical locations
- Unknown calibration status
- Timestamp mismatch
- Different signal
- No sensor winner

## Architectural finding to validate

Genesis may need to represent two distinct evidence domains:

- **asset evidence** — what may be happening to the physical asset;
- **measurement-system evidence** — whether the observation system itself is trustworthy.

This experiment does not integrate that distinction into the Genesis core. Integration should wait until the behavior is tested across robotics, energy infrastructure, and industrial equipment.
