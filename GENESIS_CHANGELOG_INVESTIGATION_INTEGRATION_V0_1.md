# Genesis Changelog — Investigation Integration v0.1

## Purpose

Connect Evidence Review with Reliability State evaluation so unresolved evidence quality or conflict prevents escalation and produces an explicit investigation plan.

## Changes

- Added `genesis_system/core/investigation.py`.
- Added `InvestigationPlan` contract.
- Added `InvestigationPlanner` for explicit follow-up actions.
- Updated `ReliabilityStateEvaluator.evaluate()` to accept an optional `EvidenceReview`.
- If evidence review blocks escalation, the evaluator returns `OBSERVATION`.
- The resulting reliability state records the evidence review and investigation plan in metadata.
- Investigation actions include independent measurement for conflicts, fresh observations for degraded evidence, restoration of unavailable sources, and integrity/provenance verification for suspected evidence.
- Existing behavior remains unchanged when no blocking review is supplied.

## Verification

`428 passed, 11 subtests passed`

## Design principle

Genesis should reduce certainty when evidence is unresolved, not manufacture certainty. `OBSERVATION` therefore becomes an active investigation state rather than a passive warning.
