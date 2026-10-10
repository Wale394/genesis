"""Lifecycle management for Genesis conflict cases.

Conflict history is immutable: an original disagreement is never rewritten.
A later investigation produces a separate resolution record that references the
original conflict and records whether the disagreement was resolved, refuted,
or remains uncertain.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Sequence

from .conflict_resolution import ConflictCase
from .evidence_contract import Evidence
from .investigation_memory import InvestigationFinding, InvestigationFindingStatus, InvestigationOutcome


class ConflictLifecycleStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    REFUTED = "REFUTED"
    STILL_UNCERTAIN = "STILL_UNCERTAIN"


@dataclass(frozen=True)
class ConflictRecord:
    """Immutable snapshot of the original disagreement."""

    conflict: ConflictCase
    opened_at: str | None = None
    original_evidence_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict": self.conflict.to_dict(),
            "opened_at": self.opened_at,
            "original_evidence_refs": list(self.original_evidence_refs),
        }


@dataclass(frozen=True)
class ConflictLifecycleUpdate:
    """A later state transition linked to an immutable conflict record."""

    conflict_id: str
    previous_status: ConflictLifecycleStatus
    status: ConflictLifecycleStatus
    investigation_id: str
    finding_refs: List[str] = field(default_factory=list)
    new_evidence_refs: List[str] = field(default_factory=list)
    resolution_reason: str = ""
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "previous_status": self.previous_status.value,
            "status": self.status.value,
            "investigation_id": self.investigation_id,
            "finding_refs": list(self.finding_refs),
            "new_evidence_refs": list(self.new_evidence_refs),
            "resolution_reason": self.resolution_reason,
            "limitations": list(self.limitations),
        }


class ConflictLifecycleEngine:
    """Reassess an existing conflict without rewriting its original history."""

    def apply_investigation(
        self,
        record: ConflictRecord,
        outcome: InvestigationOutcome,
    ) -> ConflictLifecycleUpdate:
        if not record.conflict.conflict_id:
            raise ValueError("conflict_id is required.")

        relevant_findings = [
            finding for finding in outcome.findings
            if self._finding_references_conflict(finding, record.conflict.conflict_id)
        ]

        validated = [
            finding for finding in relevant_findings
            if finding.status is InvestigationFindingStatus.VALIDATED
        ]
        refuted = [
            finding for finding in relevant_findings
            if finding.status is InvestigationFindingStatus.REFUTED
        ]

        if validated and refuted:
            status = ConflictLifecycleStatus.STILL_UNCERTAIN
            reason = "Investigation produced contradictory validated/refuted findings for the same conflict."
            limitations = ["Conflicting investigation outcomes require further review."]
        elif validated:
            status = ConflictLifecycleStatus.RESOLVED
            reason = "Investigation produced a validated finding that explicitly references the original conflict."
            limitations = []
        elif refuted:
            status = ConflictLifecycleStatus.REFUTED
            reason = "Investigation refuted the contested claim associated with the original conflict."
            limitations = []
        else:
            status = ConflictLifecycleStatus.STILL_UNCERTAIN
            reason = "Investigation did not produce a decisive finding for the original conflict."
            limitations = ["Original disagreement remains open to further evidence."]

        finding_refs = [finding.finding_id for finding in relevant_findings]
        evidence_refs = self._evidence_refs(outcome.new_evidence, outcome.new_evidence_refs)

        return ConflictLifecycleUpdate(
            conflict_id=record.conflict.conflict_id,
            previous_status=ConflictLifecycleStatus.OPEN,
            status=status,
            investigation_id=outcome.investigation_id,
            finding_refs=finding_refs,
            new_evidence_refs=evidence_refs,
            resolution_reason=reason,
            limitations=limitations,
        )

    @staticmethod
    def _finding_references_conflict(finding: InvestigationFinding, conflict_id: str) -> bool:
        if conflict_id in finding.evidence_refs:
            return True
        if finding.context.get("conflict_id") == conflict_id:
            return True
        return conflict_id in finding.context.get("conflict_ids", [])

    @staticmethod
    def _evidence_refs(evidence: Sequence[Evidence], explicit_refs: Sequence[str]) -> List[str]:
        refs = list(explicit_refs)
        for index, item in enumerate(evidence, start=1):
            ref = str(item.metadata.get("id") or f"evidence-{index:03d}")
            if ref not in refs:
                refs.append(ref)
        return refs
