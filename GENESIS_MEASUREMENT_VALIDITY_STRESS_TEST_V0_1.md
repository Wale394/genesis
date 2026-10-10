# GENESIS Measurement Validity Stress Test v0.1

## Purpose

Test whether Genesis distinguishes **semantic correctness** from **measurement validity** before treating a signal as trustworthy evidence.

This is an architectural experiment. It does **not** implement a production calibration-management subsystem.

## Hypothesis

A signal can be semantically correct while its current measurement is not trustworthy.

Example:

```text
source field -> motor_temperature -> °C
                     |
                     +-- semantics: VERIFIED
                     +-- calibration: EXPIRED
                     |
                     +-- usable as physical evidence: NO
```

## Cases tested

1. Semantic + calibrated -> usable.
2. Semantic + expired calibration -> unusable.
3. Semantic + failed calibration -> unusable.
4. Semantic + unknown calibration -> unusable.
5. Failed measurement validity cannot be overridden by semantic correctness.
6. Valid calibration cannot rescue unknown semantic meaning.
7. Invalid calibration metadata is conservative, not trusted.
8. A bad thermal measurement does not globally invalidate unrelated workload evidence.
9. Derived evidence inherits invalidity from a measurement it depends on.

## Expected boundary

```text
Source
  ↓
Semantic validity
  ↓
Measurement validity
  ↓
Observation quality
  ↓
Evidence
```

Measurement validity is therefore a **separate dimension** from semantic validity and observation quality.

## Architectural implication

Genesis should eventually be able to represent at least:

- semantic meaning is verified
- measurement validity is verified / expired / failed / unknown
- evidence dependencies
- scope of the resulting limitation

It should **not** infer calibration validity from the mere presence of a unit, a plausible numeric range, or a successful normalization step.

## Decision

Do not integrate a full calibration subsystem yet. First test this contract across robotics, energy infrastructure, and industrial equipment. If the same boundary holds across domains, promote the contract into the shared observation/evidence layer.
