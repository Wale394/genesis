import pytest

from genesis_system.core.evidence_contract import Evidence, EvidenceCategory
from genesis_system.core.evidence_review import (
    EvidenceQualityStatus,
    EvidenceReviewEngine,
)


def test_clean_evidence_allows_escalation():
    evidence = [
        Evidence(
            EvidenceCategory.DEVIATION,
            "temperature_deviation",
            8,
            "baseline_engine",
            metadata={"id": "e1", "signal": "motor_temperature", "stance": "supports"},
        ),
        Evidence(
            EvidenceCategory.TEMPORAL,
            "persistent_deviation",
            5,
            "pattern_engine",
            metadata={"id": "e2", "signal": "persistence", "stance": "supports"},
        ),
    ]

    review = EvidenceReviewEngine().review(evidence)

    assert review.overall_status is EvidenceQualityStatus.AVAILABLE
    assert review.escalation_allowed is True
    assert review.conflicts == []


def test_degraded_evidence_blocks_escalation():
    evidence = [
        Evidence(
            EvidenceCategory.DEVIATION,
            "temperature_deviation",
            8,
            "baseline_engine",
            metadata={
                "id": "e1",
                "quality_status": "DEGRADED",
                "signal": "motor_temperature",
                "stance": "supports",
            },
        )
    ]

    review = EvidenceReviewEngine().review(evidence)

    assert review.overall_status is EvidenceQualityStatus.DEGRADED
    assert review.escalation_allowed is False
    assert "additional" not in review.limitations[0]


def test_failed_security_integrity_marks_evidence_suspected():
    evidence = Evidence(
        EvidenceCategory.SECURITY,
        "telemetry_integrity",
        "failed",
        "security_layer",
        metadata={"id": "e1", "security_integrity": "FAILED"},
    )

    review = EvidenceReviewEngine().review([evidence])

    assert review.overall_status is EvidenceQualityStatus.SUSPECTED
    assert review.escalation_allowed is False


def test_conflicting_signal_blocks_escalation():
    evidence = [
        Evidence(
            EvidenceCategory.DEVIATION,
            "temperature_concern",
            8,
            "baseline_engine",
            metadata={"id": "e1", "signal": "motor_temperature", "stance": "supports"},
        ),
        Evidence(
            EvidenceCategory.CROSS_SIGNAL,
            "thermal_condition_normal",
            "normal",
            "diagnostic_engine",
            metadata={"id": "e2", "signal": "motor_temperature", "stance": "contradicts"},
        ),
    ]

    review = EvidenceReviewEngine().review(evidence)

    assert review.overall_status is EvidenceQualityStatus.AVAILABLE
    assert review.escalation_allowed is False
    assert len(review.conflicts) == 1
    assert review.conflicts[0].signal == "motor_temperature"
    assert review.conflicts[0].supporting_refs == ["e1"]
    assert review.conflicts[0].contradicting_refs == ["e2"]


def test_unrelated_signals_do_not_create_conflict():
    evidence = [
        Evidence(
            EvidenceCategory.DEVIATION,
            "temperature_concern",
            8,
            "baseline_engine",
            metadata={"id": "e1", "signal": "motor_temperature", "stance": "supports"},
        ),
        Evidence(
            EvidenceCategory.CROSS_SIGNAL,
            "voltage_normal",
            "normal",
            "diagnostic_engine",
            metadata={"id": "e2", "signal": "battery_voltage", "stance": "contradicts"},
        ),
    ]

    review = EvidenceReviewEngine().review(evidence)

    assert review.conflicts == []
    assert review.escalation_allowed is True


def test_invalid_quality_status_is_rejected():
    evidence = Evidence(
        EvidenceCategory.DEVIATION,
        "temperature_deviation",
        8,
        "baseline_engine",
        metadata={"quality_status": "MAYBE"},
    )

    with pytest.raises(ValueError, match="Invalid evidence quality status"):
        EvidenceReviewEngine().review([evidence])


def test_invalid_stance_is_rejected():
    evidence = Evidence(
        EvidenceCategory.DEVIATION,
        "temperature_deviation",
        8,
        "baseline_engine",
        metadata={"signal": "motor_temperature", "stance": "MAYBE"},
    )

    with pytest.raises(ValueError, match="Invalid evidence stance"):
        EvidenceReviewEngine().review([evidence])


def test_empty_evidence_is_not_blocked_by_quality_review():
    review = EvidenceReviewEngine().review([])

    assert review.overall_status is EvidenceQualityStatus.AVAILABLE
    assert review.escalation_allowed is True
    assert review.conflicts == []
