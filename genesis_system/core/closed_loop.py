"""Closed-loop reliability reasoning orchestration."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .evidence_contract import Evidence
from .evidence_review import EvidenceReviewEngine
from .investigation import InvestigationPlan, InvestigationPlanner
from .investigation_memory import InvestigationOutcome
from .reliability_memory import ReliabilityMemory
from .reliability_state import ReliabilityLevel, ReliabilityState, ReliabilityStateEvaluator


@dataclass(frozen=True)
class ClosedLoopResult:
    """Result of one evidence -> review -> state -> investigation cycle."""

    state: ReliabilityState
    investigation: InvestigationPlan
    memory_recorded: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.to_dict(),
            "investigation": self.investigation.to_dict(),
            "memory_recorded": self.memory_recorded,
            "metadata": dict(self.metadata),
        }


class ClosedLoopReliabilityEngine:
    """Run review, state evaluation, investigation, and validated-memory storage."""

    def __init__(self, memory: Optional[ReliabilityMemory] = None):
        self.memory = memory or ReliabilityMemory()
        self.review_engine = EvidenceReviewEngine()
        self.state_evaluator = ReliabilityStateEvaluator()
        self.investigation_planner = InvestigationPlanner()

    def assess(
        self,
        evidence: Sequence[Evidence],
        previous_level: Optional[ReliabilityLevel] = None,
        investigation_outcome: Optional[InvestigationOutcome] = None,
    ) -> ClosedLoopResult:
        items = list(evidence)
        review = self.review_engine.review(items)
        state = self.state_evaluator.evaluate(
            items,
            previous_level=previous_level,
            evidence_review=review,
        )
        investigation = self.investigation_planner.plan(items, review)

        memory_recorded = False
        if investigation_outcome is not None:
            self.memory.store_investigation(investigation_outcome)
            memory_recorded = True

        return ClosedLoopResult(
            state=state,
            investigation=investigation,
            memory_recorded=memory_recorded,
            metadata={
                "validated_finding_count": len(self.memory.validated_findings()),
            },
        )

    def close_investigation(
        self,
        prior_evidence: Sequence[Evidence],
        outcome: InvestigationOutcome,
        previous_level: Optional[ReliabilityLevel] = None,
    ) -> ClosedLoopResult:
        """Store the outcome, then reassess using the investigation's new evidence."""
        self.memory.store_investigation(outcome)
        combined = list(prior_evidence) + list(outcome.new_evidence)
        result = self.assess(
            combined,
            previous_level=previous_level,
        )
        return ClosedLoopResult(
            state=result.state,
            investigation=result.investigation,
            memory_recorded=True,
            metadata={
                **result.metadata,
                "investigation_id": outcome.investigation_id,
                "reassessment": True,
            },
        )
