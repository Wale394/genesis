# Genesis Conflict Lifecycle v0.1

## Purpose

Conflict resolution should not rewrite history. Genesis records the original disagreement as an immutable `ConflictRecord`, then records later investigation outcomes as separate lifecycle updates.

## States

- `OPEN` — original conflict exists and has not been decisively resolved.
- `RESOLVED` — a validated investigation finding explicitly references the conflict.
- `REFUTED` — an investigation finding explicitly refutes the contested claim.
- `STILL_UNCERTAIN` — the investigation produced no decisive finding, or produced contradictory findings.

## Rules

1. The original conflict is preserved unchanged.
2. A finding must explicitly reference the conflict before it can resolve it.
3. New evidence is recorded separately and can trigger another investigation cycle.
4. Contradictory validated/refuted findings never force a decision; the conflict remains uncertain.
5. Lifecycle state is an assessment of the current investigation, not a rewrite of historical evidence.
