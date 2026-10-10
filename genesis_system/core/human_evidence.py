"""Human-provided engineering evidence for Genesis.

Human evidence is recorded separately from machine-derived evidence so Genesis
can distinguish what it observed itself from what an engineer contributed.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence


class HumanEvidenceKind(str, Enum):
    HUMAN_OBSERVATION = "human_observation"
    HUMAN_INTERPRETATION = "human_interpretation"
    HUMAN_DOCUMENTATION = "human_documentation"
    HUMAN_EXPERT_ASSESSMENT = "human_expert_assessment"


class HumanClaimType(str, Enum):
    SAME_INFORMATION = "same_information"
    DISTINCT_INFORMATION = "distinct_information"
    SHARED_INFRASTRUCTURE = "shared_infrastructure"
    SEPARATE_INFRASTRUCTURE = "separate_infrastructure"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    UNKNOWN = "unknown"


class HumanEvidenceStatus(str, Enum):
    UNVALIDATED = "UNVALIDATED"
    CORROBORATED = "CORROBORATED"
    CONFLICTING = "CONFLICTING"
    VALIDATED = "VALIDATED"
    REFUTED = "REFUTED"


@dataclass(frozen=True)
class HumanEvidence:
    engineer_id: str
    role: str
    expertise: str
    claim: str
    claim_type: HumanClaimType
    basis: str
    kind: HumanEvidenceKind
    system_component: str
    timestamp: Optional[str] = None
    supporting_evidence: List[str] = field(default_factory=list)
    confidence: Optional[float] = None
    independence_key: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = {
            "engineer_id": self.engineer_id,
            "role": self.role,
            "expertise": self.expertise,
            "claim": self.claim,
            "basis": self.basis,
            "system_component": self.system_component,
        }
        for field_name, value in required.items():
            if not str(value).strip():
                raise ValueError(f"Human evidence {field_name} cannot be empty.")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Human evidence confidence must be between 0.0 and 1.0.")
        if not isinstance(self.claim_type, HumanClaimType):
            raise TypeError("claim_type must be a HumanClaimType.")
        if not isinstance(self.kind, HumanEvidenceKind):
            raise TypeError("kind must be a HumanEvidenceKind.")

    @property
    def reference(self) -> str:
        return str(self.metadata.get("id") or f"human:{self.engineer_id}:{self.claim}")

    @property
    def independence_group(self) -> str:
        """Group evidence by its stated basis; missing basis stays unknown."""
        return self.independence_key or f"UNKNOWN:{self.reference}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engineer_id": self.engineer_id,
            "role": self.role,
            "expertise": self.expertise,
            "claim": self.claim,
            "claim_type": self.claim_type.value,
            "basis": self.basis,
            "kind": self.kind.value,
            "system_component": self.system_component,
            "timestamp": self.timestamp,
            "supporting_evidence": list(self.supporting_evidence),
            "confidence": self.confidence,
            "independence_key": self.independence_key,
            "provenance": dict(self.provenance),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class HumanEvidenceReview:
    status: HumanEvidenceStatus
    target_claim: Optional[str] = None
    supporting_refs: List[str] = field(default_factory=list)
    contradicting_refs: List[str] = field(default_factory=list)
    independent_support_groups: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "target_claim": self.target_claim,
            "supporting_refs": list(self.supporting_refs),
            "contradicting_refs": list(self.contradicting_refs),
            "independent_support_groups": list(self.independent_support_groups),
            "limitations": list(self.limitations),
        }


class HumanEvidenceReviewEngine:
    """Evaluate human claims without treating one engineer as automatic truth.

    v0.1 validation requires two independently grounded supporting groups and
    no unresolved contradiction. This is a conservative default, not a final
    policy for every operational impact level.
    """

    def review(
        self,
        evidence: Sequence[HumanEvidence],
        target_claim: Optional[str] = None,
    ) -> HumanEvidenceReview:
        items = list(evidence)
        if any(not isinstance(item, HumanEvidence) for item in items):
            raise TypeError("All reviewed human evidence must be HumanEvidence instances.")
        if not items:
            return HumanEvidenceReview(HumanEvidenceStatus.UNVALIDATED, target_claim=target_claim)

        subject_claim = target_claim or items[0].claim
        supporting = [item for item in items if item.claim == subject_claim]
        contradicting = [item for item in items if item.claim != subject_claim]

        support_groups = sorted({item.independence_group for item in supporting})
        limitations: List[str] = []

        if any(item.independence_key is None for item in supporting):
            limitations.append("Some supporting human evidence has unknown independence.")

        if contradicting:
            return HumanEvidenceReview(
                status=HumanEvidenceStatus.CONFLICTING,
                target_claim=subject_claim,
                supporting_refs=[item.reference for item in supporting],
                contradicting_refs=[item.reference for item in contradicting],
                independent_support_groups=support_groups,
                limitations=limitations + [
                    "Human claims disagree about the target relationship."
                ],
            )

        if len(support_groups) >= 2:
            return HumanEvidenceReview(
                status=HumanEvidenceStatus.VALIDATED,
                target_claim=subject_claim,
                supporting_refs=[item.reference for item in supporting],
                independent_support_groups=support_groups,
                limitations=limitations,
            )

        if supporting:
            return HumanEvidenceReview(
                status=HumanEvidenceStatus.CORROBORATED,
                target_claim=subject_claim,
                supporting_refs=[item.reference for item in supporting],
                independent_support_groups=support_groups,
                limitations=limitations + [
                    "Independent human support is insufficient for v0.1 validation."
                ],
            )

        return HumanEvidenceReview(
            status=HumanEvidenceStatus.REFUTED,
            target_claim=subject_claim,
            contradicting_refs=[item.reference for item in contradicting],
            limitations=limitations,
        )
