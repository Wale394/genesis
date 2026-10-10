import pytest

from genesis_system.core.evidence_contract import Evidence, EvidenceCategory
from genesis_system.core.reliability_state import (
    ReliabilityLevel,
    ReliabilityState,
)


def test_reliability_state_serializes_without_losing_structure():
    state = ReliabilityState(
        level=ReliabilityLevel.CONCERN,
        reason="Repeated contextual deviation detected.",
        evidence_refs=["evidence-001", "evidence-002"],
        previous_level=ReliabilityLevel.OBSERVATION,
        changed=True,
        metadata={"source": "evidence_engine"},
    )

    assert state.to_dict() == {
        "level": "CONCERN",
        "reason": "Repeated contextual deviation detected.",
        "evidence_refs": ["evidence-001", "evidence-002"],
        "previous_level": "OBSERVATION",
        "changed": True,
        "metadata": {"source": "evidence_engine"},
    }


def test_reliability_state_requires_reason():
    with pytest.raises(ValueError, match="reason cannot be empty"):
        ReliabilityState(
            level=ReliabilityLevel.NORMAL,
            reason="",
        )


def test_reliability_state_rejects_invalid_previous_level():
    with pytest.raises(ValueError, match="previous_level"):
        ReliabilityState(
            level=ReliabilityLevel.NORMAL,
            reason="No concern detected.",
            previous_level="WATCH",
        )


def test_evaluator_keeps_single_evidence_at_observation():
    from genesis_system.core.reliability_state import ReliabilityStateEvaluator
    evidence = Evidence(
        category=EvidenceCategory.DEVIATION,
        name="temperature_deviation",
        value=8,
        source="baseline_engine",
        metadata={"id": "evidence-101"},
    )
    state = ReliabilityStateEvaluator().evaluate([evidence])
    assert state.level is ReliabilityLevel.OBSERVATION
    assert state.evidence_refs == ["evidence-101"]


def test_evaluator_requires_corroboration_for_concern():
    from genesis_system.core.reliability_state import ReliabilityStateEvaluator
    evidence = [
        Evidence(EvidenceCategory.DEVIATION, "temperature_deviation", 8, "baseline_engine", metadata={"id": "e1"}),
        Evidence(EvidenceCategory.TEMPORAL, "persistent_deviation", 5, "pattern_engine", metadata={"id": "e2"}),
    ]
    state = ReliabilityStateEvaluator().evaluate(evidence)
    assert state.level is ReliabilityLevel.CONCERN
    assert state.evidence_refs == ["e1", "e2"]


def test_evaluator_escalates_with_independent_corroboration():
    from genesis_system.core.reliability_state import ReliabilityStateEvaluator
    evidence = [
        Evidence(EvidenceCategory.DEVIATION, "temperature_deviation", 8, "baseline_engine", metadata={"id": "e1"}),
        Evidence(EvidenceCategory.TEMPORAL, "persistent_deviation", 5, "pattern_engine", metadata={"id": "e2"}),
        Evidence(EvidenceCategory.CROSS_SIGNAL, "voltage_correlation", "supported", "correlation_engine", metadata={"id": "e3"}),
    ]
    state = ReliabilityStateEvaluator().evaluate(evidence)
    assert state.level is ReliabilityLevel.CRITICAL
    assert state.evidence_refs == ["e1", "e2", "e3"]


def test_evaluator_preserves_previous_level_transition():
    from genesis_system.core.reliability_state import ReliabilityStateEvaluator
    state = ReliabilityStateEvaluator().evaluate([], previous_level=ReliabilityLevel.CONCERN)
    assert state.level is ReliabilityLevel.NORMAL
    assert state.previous_level is ReliabilityLevel.CONCERN
    assert state.changed is True


def test_evaluator_blocks_escalation_when_review_has_conflict():
    from genesis_system.core.evidence_review import EvidenceReviewEngine
    from genesis_system.core.reliability_state import ReliabilityStateEvaluator

    evidence = [
        Evidence(
            EvidenceCategory.DEVIATION,
            "temperature_concern",
            8,
            "baseline",
            metadata={"id": "e1", "signal": "motor_temperature", "stance": "supports"},
        ),
        Evidence(
            EvidenceCategory.CROSS_SIGNAL,
            "temperature_normal",
            "normal",
            "diagnostic",
            metadata={"id": "e2", "signal": "motor_temperature", "stance": "contradicts"},
        ),
        Evidence(
            EvidenceCategory.TEMPORAL,
            "persistent",
            5,
            "pattern",
            metadata={"id": "e3"},
        ),
    ]
    review = EvidenceReviewEngine().review(evidence)
    state = ReliabilityStateEvaluator().evaluate(evidence, evidence_review=review)

    assert state.level is ReliabilityLevel.OBSERVATION
    assert state.metadata["investigation"]["required"] is True
    assert state.changed is False


def test_evaluator_blocks_escalation_when_quality_is_degraded():
    from genesis_system.core.evidence_review import EvidenceReviewEngine
    from genesis_system.core.reliability_state import ReliabilityStateEvaluator

    evidence = [
        Evidence(
            EvidenceCategory.DEVIATION,
            "temperature_deviation",
            8,
            "baseline",
            metadata={"id": "e1", "quality_status": "DEGRADED"},
        ),
        Evidence(
            EvidenceCategory.TEMPORAL,
            "persistent",
            5,
            "pattern",
            metadata={"id": "e2"},
        ),
    ]
    review = EvidenceReviewEngine().review(evidence)
    state = ReliabilityStateEvaluator().evaluate(evidence, evidence_review=review)

    assert state.level is ReliabilityLevel.OBSERVATION
    assert state.metadata["investigation"]["required"] is True
    assert "fresh observation" in state.metadata["investigation"]["actions"][0]
