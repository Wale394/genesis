# GENESIS Measurement Disagreement Cross-Domain Stress Test v0.1

## Purpose

Test whether measurement-disagreement reasoning is domain-neutral across robotics, energy infrastructure, and industrial equipment.

This is an engineering stress test, not a production connector or product demo.

## Domains

### Robotics
- motor temperature
- two sensors at the same physical location

### Energy infrastructure
- transformer temperature
- two sensors at the same physical location

### Industrial equipment
- bearing temperature
- two sensors at the same physical location

## Expected invariant behavior

1. Agreement within tolerance supports the measurement evidence.
2. Material disagreement between current, valid measurements does not choose a winner.
3. Material disagreement requires investigation of the measurement system and/or physical asset.
4. Different physical locations are contextual differences, not automatic conflicts.
5. Stale measurements create temporal conflict.
6. Invalid measurements are not treated as equally trustworthy evidence.

## Result

15/15 focused tests passed.

The test demonstrates that the comparison mechanism can operate on domain-specific signal names without embedding robotics semantics in the disagreement logic.

## Architectural finding

The experiment strengthens the case for separating:

- evidence about the physical asset, and
- evidence about the measurement system.

No core integration is proposed from this experiment alone. The behavior should remain an experimental contract until tested against additional failure modes and real measurement provenance.
