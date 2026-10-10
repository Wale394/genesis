# Genesis Command Center V1.4 — Evidence Lineage

## Problem observed
The Evidence Explorer reported 67 nodes, 0 links, and 67 unlinked evidence items. That was a real lineage gap: pattern evidence included its source telemetry rows, but the lineage builder did not convert those embedded rows into graph relationships.

## Changes
- Add graph nodes for telemetry rows explicitly embedded in pattern evidence.
- Add `OBSERVED_IN_PATTERN_WINDOW` links from those rows to the pattern record. This represents window membership, not causation.
- Link current field-level observation evidence to an embedded row only when field/value and numeric time step match exactly, using `FIELD_VALUE_MATCH_AT_TIME_STEP`.
- Count an evidence item as linked when it has any incoming or outgoing edge.
- Expose counts for evidence items and added window-observation nodes separately.
- Display each engine graph relationship and its basis in Evidence Explorer.
- Check temporal ordering for pattern-window membership edges and surface conflicts for review.
- Preserve partial status for evidence that still has no traceable relationships.

## Verification
- `python -m pytest -q`: 600 passed, 11 additional subtests passed.
- Focused evidence/interface tests: 69 passed.
- `node --check genesis_interface/ui/app.js`: passed.
- ZIP archive integrity: verified after packaging.

## Limits
- Pattern-window membership is not proof of causation.
- Field/value/time-step equality is a traceable association, not proof that a value caused a finding.
- Findings without exposed source rows or declared references remain unlinked.
- The default scenario uses synthetic telemetry processed by the real Genesis engine; it is not a live sensor connection.
