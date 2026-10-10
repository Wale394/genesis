# Genesis Conflict Resolution & Investigation v0.1

## Purpose

Add an auditable conflict layer between Evidence Review and Investigation without introducing majority voting or a second investigation system.

## Added

- `genesis_system/core/conflict_resolution.py`
- root compatibility shim: `conflict_resolution.py`
- `test_conflict_resolution.py`

## Conflict types

- MACHINE
- HUMAN
- MACHINE_HUMAN

## Resolution states

- NO_CONFLICT
- INVESTIGATION_REQUIRED
- UNRESOLVED

v0.1 intentionally does not automatically declare a disputed claim true or false. Unresolved disagreement becomes an investigation requirement.

## Rules

1. Machine evidence conflicts remain machine conflicts even when human evidence is validated.
2. Human disagreement becomes a human conflict case.
3. Validated human evidence cannot erase a machine-side conflict.
4. Conflict cases preserve supporting and contradicting evidence references.
5. Each conflict produces explicit questions for investigation.
6. Existing `InvestigationPlanner` is reused; no parallel investigation system is introduced.
7. Resolution requires new evidence and reassessment through the existing closed loop.

## Verification

Focused conflict tests: 4 passed.

Full pytest suite: 454 passed, 11 subtests passed.
