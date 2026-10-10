# Genesis Changelog — Reliability Memory Retrieval v0.1

## Purpose

Add controlled retrieval of historical investigation findings without promoting historical memory into current truth.

## Added

- `genesis_system/core/reliability_memory_retrieval.py`
- `MemoryQuery`
- `MemoryMatch`
- `ReliabilityMemoryRetriever`
- `test_reliability_memory_retrieval.py`

## Retrieval rules

1. Retrieval uses explicit structured context in v0.1.
2. Text similarity is intentionally not used.
3. `VALIDATED` findings may be returned as validated historical findings.
4. `OBSERVED` and `HYPOTHESIS` findings remain unresolved historical context.
5. `REFUTED` findings remain explicitly refuted historical context.
6. Conflicting validated/refuted findings sharing the same explicit context produce `CONFLICTING` retrieval status.
7. Historical retrieval does not establish causality or current-state equivalence.
8. Historical memory does not directly change reliability state or make decisions.

## Verification

Focused tests: 5 passed.
Full regression: 464 passed, 11 subtests passed.
