# Genesis Human Evidence Review Integration v0.1

## Purpose
Integrate human-provided engineering evidence into Evidence Review without collapsing machine-derived and human-derived reasoning.

## Added
- `CombinedEvidenceReview` result contract.
- `EvidenceReviewEngine.review_combined(...)`.
- Separate machine-only and human-assisted assessment modes.
- Human conflict/refutation blocks the human-assisted path.
- Machine evidence conflicts or degraded quality cannot be overridden by human input.
- Independently grounded human evidence can produce `HUMAN_VALIDATED`.
- Corroborated but non-independent human evidence produces `HUMAN_INFORMED` rather than validation.

## Preserved
- Existing `EvidenceReviewEngine.review(...)` behavior.
- Existing machine evidence quality and conflict rules.
- Human evidence provenance and independence rules.

## Verification
- Focused tests: 22 passed.
- Full regression: 450 passed, 11 subtests passed.
