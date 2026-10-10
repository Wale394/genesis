# Genesis Changelog — Memory Provenance & Trust v0.1

## Purpose

Add explicit provenance and conservative reuse rules to historical reliability memory without introducing a numeric trust score.

## Added

- `genesis_system/core/memory_provenance.py`
- `MemoryProvenance`
- `MemorySourceType`
- `ProvenanceStatus`
- `MemoryReuseStance`
- `assess_memory_reuse`
- provenance fields on `InvestigationFinding`
- provenance and reuse metadata on `MemoryMatch`

## Rules

1. Historical memory does not become current truth merely because it was retrieved.
2. `VALIDATED` findings with complete source, evidence, and validation references may support reuse.
3. `VALIDATED` findings with incomplete provenance remain usable only with caution.
4. `OBSERVED` and `HYPOTHESIS` findings remain cautionary context even when provenance is complete.
5. `REFUTED` findings are explicitly excluded from supporting reuse, while remaining available as historical negative evidence.
6. No numeric trust score is used in v0.1.
7. Provenance is preserved with the finding so the basis for reuse remains auditable.

## Verification

Focused tests: 10 passed.
Full regression: 469 passed, 11 subtests passed.
