"""Evidence quality and conflict review for reliability decisions.

This layer does not decide the reliability state. It determines whether the
current evidence is trustworthy and internally consistent enough to support
an escalation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Sequence

from .evidence_contract import Evidence
from .human_evidence import (
    HumanEvidence,
    HumanEvidenceReview,
    HumanEvidenceReviewEngine,
    HumanEvidenceStatus,
)


class EvidenceQualityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    SUSPECTED = "SUSPECTED"


class EvidenceStance(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class EvidenceConflict:
    """A contradiction between evidence about the same declared signal."""

    signal: str
    supporting_refs: List[str] = field(default_factory=list)
    contradicting_refs: List[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal": self.signal,
            "supporting_refs": list(self.supporting_refs),
            "contradicting_refs": list(self.contradicting_refs),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class EvidenceReview:
    """Review result consumed later by reliability-state policy."""

    overall_status: EvidenceQualityStatus
    escalation_allowed: bool
    evidence_statuses: Dict[str, EvidenceQualityStatus] = field(default_factory=dict)
    conflicts: List[EvidenceConflict] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "escalation_allowed": self.escalation_allowed,
            "evidence_statuses": {
                ref: status.value for ref, status in self.evidence_statuses.items()
            },
            "conflicts": [item.to_dict() for item in self.conflicts],
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class CombinedEvidenceReview:
    """Separate machine-only and human-assisted evidence assessments."""

    machine_review: EvidenceReview
    human_review: HumanEvidenceReview
    human_assisted_allowed: bool
    assessment_mode: str
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "machine_review": self.machine_review.to_dict(),
            "human_review": self.human_review.to_dict(),
            "human_assisted_allowed": self.human_assisted_allowed,
            "assessment_mode": self.assessment_mode,
            "limitations": list(self.limitations),
        }


class EvidenceReviewEngine:
    """Review evidence quality and explicit signal conflicts.

    The engine intentionally does not infer that two evidence items are
    independent merely because they have different categories. Independence
    remains a future policy concern for the reliability evaluator.
    """

    _QUALITY_ORDER = (
        EvidenceQualityStatus.SUSPECTED,
        EvidenceQualityStatus.UNAVAILABLE,
        EvidenceQualityStatus.DEGRADED,
        EvidenceQualityStatus.AVAILABLE,
    )

    def review(self, evidence: Sequence[Evidence]) -> EvidenceReview:
        items = list(evidence)
        if any(not isinstance(item, Evidence) for item in items):
            raise TypeError("All reviewed evidence must be Evidence instances.")

        refs = [self._reference(item, index) for index, item in enumerate(items)]
        statuses = {
            ref: self._quality_status(item)
            for ref, item in zip(refs, items)
        }
        conflicts = self._find_conflicts(items, refs)

        overall_status = self._overall_status(statuses.values())
        limitations = []
        if overall_status is not EvidenceQualityStatus.AVAILABLE:
            limitations.append(
                f"Evidence quality is {overall_status.value.lower()}; escalation requires review."
            )
        if conflicts:
            limitations.append(
                "Conflicting evidence is unresolved; additional investigation is required."
            )

        escalation_allowed = (
            overall_status is EvidenceQualityStatus.AVAILABLE and not conflicts
        )

        return EvidenceReview(
            overall_status=overall_status,
            escalation_allowed=escalation_allowed,
            evidence_statuses=statuses,
            conflicts=conflicts,
            limitations=limitations,
        )

    def review_combined(
        self,
        evidence: Sequence[Evidence],
        human_evidence: Sequence[HumanEvidence],
        target_claim: str | None = None,
    ) -> CombinedEvidenceReview:
        """Review machine and human evidence without collapsing their provenance.

        Machine review remains authoritative for machine evidence quality and
        conflicts. Human input can inform the assessment, but unresolved human
        conflict or refutation prevents the human-assisted path from being
        treated as validated.
        """
        machine_review = self.review(evidence)
        human_review = HumanEvidenceReviewEngine().review(
            human_evidence, target_claim=target_claim
        )
        limitations = list(machine_review.limitations) + list(human_review.limitations)

        if not human_evidence:
            return CombinedEvidenceReview(
                machine_review=machine_review,
                human_review=human_review,
                human_assisted_allowed=machine_review.escalation_allowed,
                assessment_mode="MACHINE_ONLY",
                limitations=limitations,
            )

        if human_review.status in (
            HumanEvidenceStatus.CONFLICTING,
            HumanEvidenceStatus.REFUTED,
        ):
            limitations.append(
                "Human evidence is unresolved; the human-assisted assessment cannot be treated as validated."
            )
            return CombinedEvidenceReview(
                machine_review=machine_review,
                human_review=human_review,
                human_assisted_allowed=False,
                assessment_mode="CONFLICTING_HUMAN_EVIDENCE",
                limitations=limitations,
            )

        if not machine_review.escalation_allowed:
            limitations.append(
                "Machine evidence quality or conflict prevents human input from authorizing escalation."
            )
            return CombinedEvidenceReview(
                machine_review=machine_review,
                human_review=human_review,
                human_assisted_allowed=False,
                assessment_mode="MACHINE_LIMITED",
                limitations=limitations,
            )

        if human_review.status is HumanEvidenceStatus.VALIDATED:
            mode = "HUMAN_VALIDATED"
        else:
            mode = "HUMAN_INFORMED"
            limitations.append(
                "Human evidence is not independently validated; it informs but does not establish the finding alone."
            )

        return CombinedEvidenceReview(
            machine_review=machine_review,
            human_review=human_review,
            human_assisted_allowed=True,
            assessment_mode=mode,
            limitations=limitations,
        )

    @classmethod
    def _quality_status(cls, item: Evidence) -> EvidenceQualityStatus:
        raw = item.metadata.get("quality_status", EvidenceQualityStatus.AVAILABLE.value)
        try:
            status = EvidenceQualityStatus(str(raw).upper())
        except ValueError as exc:
            raise ValueError(
                f"Invalid evidence quality status: {raw!r}."
            ) from exc

        if item.metadata.get("security_integrity") == "FAILED":
            return EvidenceQualityStatus.SUSPECTED
        return status

    @classmethod
    def _overall_status(
        cls, statuses: Sequence[EvidenceQualityStatus]
    ) -> EvidenceQualityStatus:
        if not statuses:
            return EvidenceQualityStatus.AVAILABLE
        for status in cls._QUALITY_ORDER:
            if status in statuses:
                return status
        return EvidenceQualityStatus.AVAILABLE

    @staticmethod
    def _find_conflicts(
        items: Sequence[Evidence], refs: Sequence[str]
    ) -> List[EvidenceConflict]:
        grouped: Dict[str, Dict[str, List[str]]] = {}
        for ref, item in zip(refs, items):
            signal = item.metadata.get("signal")
            stance = item.metadata.get("stance")
            if not signal or not stance:
                continue
            try:
                normalized = EvidenceStance(str(stance).upper())
            except ValueError as exc:
                raise ValueError(
                    f"Invalid evidence stance: {stance!r}."
                ) from exc
            if normalized is EvidenceStance.NEUTRAL:
                continue
            bucket = grouped.setdefault(
                str(signal),
                {
                    EvidenceStance.SUPPORTS.value: [],
                    EvidenceStance.CONTRADICTS.value: [],
                },
            )
            bucket[normalized.value].append(ref)

        conflicts = []
        for signal, bucket in grouped.items():
            supporting = bucket[EvidenceStance.SUPPORTS.value]
            contradicting = bucket[EvidenceStance.CONTRADICTS.value]
            if supporting and contradicting:
                conflicts.append(
                    EvidenceConflict(
                        signal=signal,
                        supporting_refs=supporting,
                        contradicting_refs=contradicting,
                        reason="Evidence producers disagree about the declared signal.",
                    )
                )
        return conflicts

    @staticmethod
    def _reference(item: Evidence, index: int) -> str:
        return str(item.metadata.get("id") or f"evidence-{index + 1:03d}")
