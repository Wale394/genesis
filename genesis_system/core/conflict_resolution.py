"""Conflict classification and investigation planning for Genesis.

This layer does not vote between machine and human evidence. It records what
conflicts exist, preserves provenance, and turns unresolved disagreement into
explicit investigative work using the existing InvestigationPlanner.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Sequence

from .evidence_contract import Evidence
from .evidence_review import CombinedEvidenceReview, EvidenceReview
from .human_evidence import HumanEvidence, HumanEvidenceStatus
from .investigation import InvestigationPlan, InvestigationPlanner


class ConflictType(str, Enum):
    MACHINE = "MACHINE"
    HUMAN = "HUMAN"
    MACHINE_HUMAN = "MACHINE_HUMAN"


class ConflictResolutionStatus(str, Enum):
    NO_CONFLICT = "NO_CONFLICT"
    INVESTIGATION_REQUIRED = "INVESTIGATION_REQUIRED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class ConflictCase:
    """Auditable description of an unresolved disagreement."""

    conflict_id: str
    conflict_type: ConflictType
    subject: str
    supporting_refs: List[str] = field(default_factory=list)
    contradicting_refs: List[str] = field(default_factory=list)
    reason: str = ""
    status: ConflictResolutionStatus = ConflictResolutionStatus.INVESTIGATION_REQUIRED
    required_questions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "subject": self.subject,
            "supporting_refs": list(self.supporting_refs),
            "contradicting_refs": list(self.contradicting_refs),
            "reason": self.reason,
            "status": self.status.value,
            "required_questions": list(self.required_questions),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class ConflictResolutionResult:
    """Conflict assessment plus the existing investigation plan."""

    status: ConflictResolutionStatus
    cases: List[ConflictCase] = field(default_factory=list)
    investigation: InvestigationPlan | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "cases": [case.to_dict() for case in self.cases],
            "investigation": self.investigation.to_dict() if self.investigation else None,
        }


class ConflictResolutionEngine:
    """Classify disagreements without resolving them by majority vote."""

    def __init__(self, investigation_planner: InvestigationPlanner | None = None):
        self.investigation_planner = investigation_planner or InvestigationPlanner()

    def review(
        self,
        evidence: Sequence[Evidence],
        machine_review: EvidenceReview,
        combined_review: CombinedEvidenceReview | None = None,
        human_evidence: Sequence[HumanEvidence] = (),
    ) -> ConflictResolutionResult:
        items = list(evidence)
        humans = list(human_evidence)
        cases: List[ConflictCase] = []

        for index, conflict in enumerate(machine_review.conflicts, start=1):
            cases.append(
                ConflictCase(
                    conflict_id=f"machine-conflict-{index:03d}",
                    conflict_type=ConflictType.MACHINE,
                    subject=conflict.signal,
                    supporting_refs=list(conflict.supporting_refs),
                    contradicting_refs=list(conflict.contradicting_refs),
                    reason=conflict.reason,
                    required_questions=[
                        f"Which observation or source explains the disagreement about {conflict.signal}?",
                        "Can an independent measurement distinguish the competing explanations?",
                    ],
                )
            )

        if combined_review is not None:
            human_review = combined_review.human_review
            if human_review.status is HumanEvidenceStatus.CONFLICTING:
                cases.append(
                    ConflictCase(
                        conflict_id=f"human-conflict-{len(cases) + 1:03d}",
                        conflict_type=ConflictType.HUMAN,
                        subject=human_review.target_claim or "human_claim",
                        supporting_refs=list(human_review.supporting_refs),
                        contradicting_refs=list(human_review.contradicting_refs),
                        reason="Independent human claims disagree about the target relationship.",
                        required_questions=[
                            "What independent evidence can distinguish the competing engineering claims?",
                            "Are the engineers relying on different physical, documentary, or observational bases?",
                        ],
                    )
                )

            if human_review.status is HumanEvidenceStatus.REFUTED:
                cases.append(
                    ConflictCase(
                        conflict_id=f"human-refuted-{len(cases) + 1:03d}",
                        conflict_type=ConflictType.HUMAN,
                        subject=human_review.target_claim or "human_claim",
                        contradicting_refs=list(human_review.contradicting_refs),
                        reason="Human evidence does not support the requested target claim.",
                        required_questions=[
                            "What evidence is needed to establish the target claim independently?",
                        ],
                    )
                )

            # A validated human relationship cannot override a machine conflict;
            # the combined review already marks this as machine-limited. Preserve
            # that distinction as a cross-domain investigation case.
            if machine_review.conflicts and human_review.status is HumanEvidenceStatus.VALIDATED:
                cases.append(
                    ConflictCase(
                        conflict_id=f"machine-human-conflict-{len(cases) + 1:03d}",
                        conflict_type=ConflictType.MACHINE_HUMAN,
                        subject=human_review.target_claim or "cross_domain_assessment",
                        supporting_refs=list(human_review.supporting_refs),
                        contradicting_refs=[
                            ref
                            for conflict in machine_review.conflicts
                            for ref in conflict.contradicting_refs
                        ],
                        reason="Validated human evidence does not eliminate an unresolved machine evidence conflict.",
                        required_questions=[
                            "Does the human claim explain the machine disagreement, or is a separate machine-side fault present?",
                            "What independent technical evidence can test both explanations?",
                        ],
                        limitations=[
                            "Human validation and machine conflict must remain separately auditable.",
                        ],
                    )
                )

        if not cases:
            return ConflictResolutionResult(
                status=ConflictResolutionStatus.NO_CONFLICT,
                investigation=self.investigation_planner.plan(items, machine_review),
            )

        investigation = self.investigation_planner.plan(items, machine_review)
        extra_actions = []
        for case in cases:
            extra_actions.extend(case.required_questions)
        investigation = InvestigationPlan(
            required=True,
            reasons=list(investigation.reasons) + [case.reason for case in cases],
            actions=list(dict.fromkeys(list(investigation.actions) + extra_actions)),
            evidence_refs=list(dict.fromkeys(
                list(investigation.evidence_refs)
                + [ref for case in cases for ref in case.supporting_refs + case.contradicting_refs]
            )),
        )

        return ConflictResolutionResult(
            status=ConflictResolutionStatus.INVESTIGATION_REQUIRED,
            cases=cases,
            investigation=investigation,
        )
