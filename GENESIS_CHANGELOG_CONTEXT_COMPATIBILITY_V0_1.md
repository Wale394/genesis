# Genesis Context Compatibility v0.1

## Purpose

Context Compatibility determines whether a validated historical reliability finding is reasonably relevant to a current case.

It is a **relevance assessment**, not a truth or causality assessment.

## Contract

### Context relationships

- `SAME`
- `DIFFERENT`
- `UNKNOWN`

Each comparison records:

- dimension
- historical value
- current value
- relationship
- whether the dimension is material
- reason

### Compatibility states

- `COMPATIBLE`
- `PARTIALLY_COMPATIBLE`
- `INCOMPATIBLE`
- `UNKNOWN`

## v0.1 rules

1. No comparisons -> `UNKNOWN` and investigation required.
2. Any **material** `UNKNOWN` -> `UNKNOWN` and investigation required.
3. Material `DIFFERENT` plus material `SAME` -> `PARTIALLY_COMPATIBLE` and investigation required.
4. Material `DIFFERENT` with no material match -> `INCOMPATIBLE`.
5. All compared material dimensions `SAME` -> `COMPATIBLE`.
6. Non-material differences do not block compatibility.
7. `UNKNOWN` is never treated as compatible.
8. The evaluator uses no numeric compatibility score.

## Architectural boundary

Context Compatibility does not establish that a historical cause is true again. A compatible historical finding may be used as historical supporting context; partial compatibility and material unknowns require investigation before substantive reuse.

The evaluator intentionally does not decide which dimensions are material. That determination belongs to the system/domain configuration or explicit engineering knowledge.

## Validation

Focused tests: **7 passed**

Full regression after integration: **476 passed, 11 subtests passed**
