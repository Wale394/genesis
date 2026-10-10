# Genesis Reliability State v0.2

## Change
Added `ReliabilityStateEvaluator` to the domain-neutral core reliability state contract.

## Design
- Uses explicit evidence-category rules, not weighted scoring.
- A single evidence item produces `OBSERVATION`.
- Deviation plus one corroborating evidence category produces `CONCERN`.
- Deviation plus two corroborating categories produces `CRITICAL`.
- Explicit producer metadata `severity=critical` can directly produce `CRITICAL`.
- No evidence produces `NORMAL`.
- Previous state and transition information are preserved.
- Evidence references are returned with the state for traceability.

## Verification
`414 passed, 11 subtests passed`
