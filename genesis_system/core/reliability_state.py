"""Domain-neutral reliability state contract.

This module defines the shared representation of a reliability state.
Domain-specific state transition policy remains outside this contract.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .evidence_contract import Evidence, EvidenceCategory
from .evidence_review import EvidenceReview
from .investigation import InvestigationPlanner


class ReliabilityLevel(str, Enum):
    """Ordered operational concern levels shared by Genesis domains."""

    NORMAL = "NORMAL"
    OBSERVATION = "OBSERVATION"
    CONCERN = "CONCERN"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ReliabilityState:
    """Structured reliability state produced from accumulated evidence."""

    level: ReliabilityLevel
    reason: str
    evidence_refs: List[str] = field(default_factory=list)
    previous_level: Optional[ReliabilityLevel] = None
    changed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("Reliability state reason cannot be empty.")

        if self.previous_level is not None and not isinstance(
            self.previous_level, ReliabilityLevel
        ):
            raise ValueError("previous_level must be a ReliabilityLevel or None.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "previous_level": (
                self.previous_level.value
                if self.previous_level is not None
                else None
            ),
            "changed": self.changed,
            "metadata": dict(self.metadata),
        }


class ReliabilityStateEvaluator:
    """Evaluate structured evidence using explicit, inspectable rules.

    This is policy, not a scoring model. It deliberately avoids weighted
    evidence and returns the evidence references used by the decision.
    """

    _CORROBORATING_CATEGORIES = {
        EvidenceCategory.TEMPORAL,
        EvidenceCategory.PATTERN,
        EvidenceCategory.CONTEXT,
        EvidenceCategory.CROSS_SIGNAL,
        EvidenceCategory.HISTORICAL,
    }

    def evaluate(
        self,
        evidence: Sequence[Evidence],
        previous_level: Optional[ReliabilityLevel] = None,
        evidence_review: Optional[EvidenceReview] = None,
    ) -> ReliabilityState:
        items = list(evidence)
        if any(not isinstance(item, Evidence) for item in items):
            raise TypeError("All reliability evidence must be Evidence instances.")

        refs = [self._reference(item, index) for index, item in enumerate(items)]

        # Unresolved evidence quality or conflict blocks escalation. Genesis
        # stays at OBSERVATION until an investigation produces better evidence.
        if evidence_review is not None and not evidence_review.escalation_allowed:
            investigation = InvestigationPlanner().plan(items, evidence_review)
            return ReliabilityState(
                level=ReliabilityLevel.OBSERVATION,
                reason="Evidence quality or conflict is unresolved; investigation is required before escalation.",
                evidence_refs=refs,
                previous_level=previous_level,
                changed=previous_level is not None and previous_level != ReliabilityLevel.OBSERVATION,
                metadata={
                    "evidence_review": evidence_review.to_dict(),
                    "investigation": investigation.to_dict(),
                },
            )

        critical_refs = [
            ref
            for ref, item in zip(refs, items)
            if item.metadata.get("severity") == "critical"
        ]

        categories = {item.category for item in items}
        corroborating = categories & self._CORROBORATING_CATEGORIES
        has_deviation = EvidenceCategory.DEVIATION in categories

        if critical_refs:
            level = ReliabilityLevel.CRITICAL
            reason = "Critical evidence explicitly reported by an evidence producer."
            supporting_refs = critical_refs
        elif has_deviation and len(corroborating) >= 2:
            level = ReliabilityLevel.CRITICAL
            reason = "Deviation is supported by multiple independent evidence dimensions."
            supporting_refs = refs
        elif has_deviation and len(corroborating) >= 1:
            level = ReliabilityLevel.CONCERN
            reason = "Deviation is corroborated by additional temporal, contextual, historical, pattern, or cross-signal evidence."
            supporting_refs = refs
        elif len(items) >= 2 and len(categories) >= 2:
            level = ReliabilityLevel.CONCERN
            reason = "Multiple distinct evidence categories indicate a reliability concern."
            supporting_refs = refs
        elif items:
            level = ReliabilityLevel.OBSERVATION
            reason = "Evidence indicates behavior worth observing, but does not yet establish a reliability concern."
            supporting_refs = refs
        else:
            level = ReliabilityLevel.NORMAL
            reason = "No reliability evidence requiring elevated attention was provided."
            supporting_refs = []

        changed = previous_level is not None and previous_level != level
        return ReliabilityState(
            level=level,
            reason=reason,
            evidence_refs=supporting_refs,
            previous_level=previous_level,
            changed=changed,
        )

    @staticmethod
    def _reference(item: Evidence, index: int) -> str:
        return str(item.metadata.get("id") or f"evidence-{index + 1:03d}")
