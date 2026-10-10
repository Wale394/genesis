# Genesis Human Evidence v0.1

## Purpose

Introduce a separate contract for engineer-provided knowledge so Genesis can distinguish machine-derived assessments from human contributions.

## Added

- `genesis_system/core/human_evidence.py`
  - `HumanEvidenceKind`
  - `HumanClaimType`
  - `HumanEvidenceStatus`
  - `HumanEvidence`
  - `HumanEvidenceReview`
  - `HumanEvidenceReviewEngine`
- Root compatibility shim: `human_evidence.py`
- `test_human_evidence.py`

## Design rules

1. Human evidence is separate from machine evidence.
2. Engineer claims carry provenance, basis, expertise, role, and supporting evidence.
3. One engineer does not automatically validate a high-stakes relationship.
4. Multiple engineers sharing the same underlying basis do not count as independent confirmations.
5. Two independently grounded supporting groups can validate a claim in v0.1.
6. Contradictory human claims remain explicitly `CONFLICTING`.
7. Machine-only and human-assisted assessments remain distinguishable.
8. Unknown independence is not silently treated as independent.

## Validation

- Focused human-evidence tests: 8 passed.
- Full Genesis regression suite: 444 passed, 11 subtests passed.

## Scope boundary

This release defines the human evidence contract and conservative review policy. It does not yet integrate human evidence into the production Evidence Review pipeline, Reliability State evaluator, investigation lifecycle, or Reliability Memory. Those integrations should follow only after the contract is reviewed and accepted.
