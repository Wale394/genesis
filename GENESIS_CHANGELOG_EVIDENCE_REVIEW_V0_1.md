# Genesis Evidence Conflict & Quality Layer v0.1

## Purpose

Add a domain-neutral review layer that determines whether evidence is trustworthy
and internally consistent enough to support a future reliability-state escalation.

## Added

- `genesis_system/core/evidence_review.py`
- root compatibility shim: `evidence_review.py`
- `test_evidence_review.py`

## Quality states

- `AVAILABLE` — evidence is usable.
- `DEGRADED` — evidence is usable with limitations; escalation is blocked.
- `UNAVAILABLE` — evidence cannot currently support escalation.
- `SUSPECTED` — evidence should not be trusted, including failed declared security integrity.

## Conflict handling

Evidence producers can declare:

- `metadata["signal"]` — the signal being assessed.
- `metadata["stance"]` — `SUPPORTS`, `CONTRADICTS`, or `NEUTRAL`.

If evidence about the same declared signal contains both supporting and
contradicting stances, the review records an explicit conflict and blocks
escalation. It does not average the disagreement away.

## Important boundary

This layer does **not** determine `NORMAL`, `OBSERVATION`, `CONCERN`, or
`CRITICAL`. It produces a review result that the Reliability State Evaluator
will use in the next integration step.

The layer also does not assume that different evidence categories are
statistically independent. That remains a separate reliability-policy problem.
