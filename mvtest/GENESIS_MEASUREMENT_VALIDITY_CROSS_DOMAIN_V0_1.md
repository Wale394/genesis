# GENESIS Measurement Validity — Cross-Domain Stress Test v0.1

## Purpose

Test whether measurement validity can remain a domain-neutral reasoning contract across robotics, energy infrastructure, and industrial equipment without allowing a failed measurement to globally poison unrelated evidence.

This is an engineering experiment, not a production calibration subsystem.

## Hypothesis

Genesis should distinguish:

1. semantic validity — what the signal means;
2. measurement validity — whether the current measurement can be trusted;
3. observation quality — whether the observation is usable;
4. evidence — what a conclusion may legitimately depend on.

Measurement validity should propagate through evidence dependencies, not globally across the asset.

## Scenarios

### Robotics
- motor temperature calibration failed
- workload remains valid
- thermal evidence becomes unusable
- workload evidence remains usable

### Energy infrastructure
- transformer temperature calibration expired
- line current remains valid
- thermal-stress evidence becomes unusable
- load-behavior evidence remains usable

### Industrial equipment
- spindle vibration verification failed
- production rate remains valid
- vibration evidence becomes unusable
- throughput evidence remains usable

## Conservative rule

Unknown measurement validity is not treated as valid.

A semantically correct signal with unknown or failed measurement validity cannot be used as measurement evidence.

## Cross-domain result

**15/15 tests passed.**

The same reasoning contract held across all three domains.

## Architectural conclusion

Measurement validity is a strong candidate for the shared Genesis layer because the contract concerns evidence trust and dependency propagation rather than a particular physical domain.

However, this does **not** justify building a full calibration-management subsystem yet. The next stress test should attack harder measurement cases such as:

- intermittent sensor failure;
- stale-but-calibrated measurements;
- redundant sensors that disagree;
- calibration valid but sensor physically disconnected;
- maintenance/replacement events that invalidate historical comparability;
- derived signals whose validity depends on multiple measurements.

Only after these cases are understood should the contract be considered for integration into the shared core.
