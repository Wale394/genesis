"""Investigation planning for unresolved reliability evidence."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

from .evidence_contract import Evidence
from .evidence_review import EvidenceReview, EvidenceQualityStatus


@dataclass(frozen=True)
class InvestigationPlan:
    """Structured follow-up work required to reduce unresolved uncertainty."""

    required: bool
    reasons: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "required": self.required,
            "reasons": list(self.reasons),
            "actions": list(self.actions),
            "evidence_refs": list(self.evidence_refs),
        }


class InvestigationPlanner:
    """Turn evidence-review limitations into explicit next investigative steps."""

    def plan(
        self,
        evidence: Sequence[Evidence],
        review: EvidenceReview,
    ) -> InvestigationPlan:
        items = list(evidence)
        refs = [self._reference(item, index) for index, item in enumerate(items)]

        if review.escalation_allowed:
            return InvestigationPlan(required=False, evidence_refs=refs)

        reasons = list(review.limitations)
        actions: List[str] = []

        if review.conflicts:
            actions.append("Collect an independent measurement for each conflicting signal.")
            actions.append("Identify which evidence source or producer explains the disagreement.")

        if review.overall_status is EvidenceQualityStatus.DEGRADED:
            actions.append("Improve observation quality and collect a fresh observation.")
        elif review.overall_status is EvidenceQualityStatus.UNAVAILABLE:
            actions.append("Restore the missing evidence source before escalation.")
        elif review.overall_status is EvidenceQualityStatus.SUSPECTED:
            actions.append("Verify source integrity and provenance before trusting new evidence.")

        if not actions:
            actions.append("Collect additional independent evidence before escalating reliability state.")

        return InvestigationPlan(
            required=True,
            reasons=reasons,
            actions=actions,
            evidence_refs=refs,
        )

    @staticmethod
    def _reference(item: Evidence, index: int) -> str:
        return str(item.metadata.get("id") or f"evidence-{index + 1:03d}")
