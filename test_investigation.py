from genesis_system.core.evidence_contract import Evidence, EvidenceCategory
from genesis_system.core.evidence_review import EvidenceReviewEngine
from genesis_system.core.investigation import InvestigationPlanner


def test_clean_review_requires_no_investigation():
    evidence = [
        Evidence(EvidenceCategory.DEVIATION, "temperature_deviation", 8, "baseline", metadata={"id": "e1"})
    ]
    review = EvidenceReviewEngine().review(evidence)
    plan = InvestigationPlanner().plan(evidence, review)

    assert plan.required is False
    assert plan.actions == []


def test_conflict_requests_independent_measurement():
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
    ]
    review = EvidenceReviewEngine().review(evidence)
    plan = InvestigationPlanner().plan(evidence, review)

    assert plan.required is True
    assert any("independent measurement" in action for action in plan.actions)
    assert plan.evidence_refs == ["e1", "e2"]


def test_degraded_quality_requests_fresh_observation():
    evidence = [
        Evidence(
            EvidenceCategory.DEVIATION,
            "temperature_deviation",
            8,
            "baseline",
            metadata={"id": "e1", "quality_status": "DEGRADED"},
        )
    ]
    review = EvidenceReviewEngine().review(evidence)
    plan = InvestigationPlanner().plan(evidence, review)

    assert plan.required is True
    assert any("fresh observation" in action for action in plan.actions)


def test_suspected_integrity_requests_provenance_verification():
    evidence = [
        Evidence(
            EvidenceCategory.SECURITY,
            "telemetry_integrity",
            "failed",
            "security",
            metadata={"id": "e1", "security_integrity": "FAILED"},
        )
    ]
    review = EvidenceReviewEngine().review(evidence)
    plan = InvestigationPlanner().plan(evidence, review)

    assert plan.required is True
    assert any("integrity and provenance" in action for action in plan.actions)
