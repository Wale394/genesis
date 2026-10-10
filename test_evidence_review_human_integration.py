from genesis_system.core.evidence_contract import Evidence, EvidenceCategory
from genesis_system.core.evidence_review import EvidenceReviewEngine
from genesis_system.core.human_evidence import (
    HumanEvidence,
    HumanEvidenceKind,
    HumanClaimType,
    HumanEvidenceStatus,
)


def machine():
    return [Evidence(
        EvidenceCategory.DEVIATION,
        "temperature_deviation",
        8,
        "baseline_engine",
        metadata={"id": "m1", "signal": "motor_temperature", "stance": "supports"},
    )]


def human(engineer, claim, basis, key, ref):
    return HumanEvidence(
        engineer_id=engineer,
        role="controls engineer",
        expertise="motor systems",
        claim=claim,
        claim_type=HumanClaimType.SAME_INFORMATION,
        basis=basis,
        kind=HumanEvidenceKind.HUMAN_EXPERT_ASSESSMENT,
        system_component="motor-controller",
        independence_key=key,
        metadata={"id": ref},
    )


def test_no_human_evidence_preserves_machine_only_path():
    result = EvidenceReviewEngine().review_combined(machine(), [])
    assert result.assessment_mode == "MACHINE_ONLY"
    assert result.human_assisted_allowed is True
    assert result.machine_review.escalation_allowed is True


def test_validated_human_evidence_creates_human_validated_path():
    humans = [
        human("A", "A and B measure the same thing", "manufacturer documentation", "doc", "h1"),
        human("B", "A and B measure the same thing", "hardware inspection", "inspection", "h2"),
    ]
    result = EvidenceReviewEngine().review_combined(
        machine(), humans, target_claim="A and B measure the same thing"
    )
    assert result.human_review.status is HumanEvidenceStatus.VALIDATED
    assert result.assessment_mode == "HUMAN_VALIDATED"
    assert result.human_assisted_allowed is True


def test_same_human_basis_does_not_validate_combined_path():
    humans = [
        human("A", "A and B measure the same thing", "same document", "doc", "h1"),
        human("B", "A and B measure the same thing", "same document", "doc", "h2"),
    ]
    result = EvidenceReviewEngine().review_combined(
        machine(), humans, target_claim="A and B measure the same thing"
    )
    assert result.human_review.status is HumanEvidenceStatus.CORROBORATED
    assert result.assessment_mode == "HUMAN_INFORMED"
    assert result.human_assisted_allowed is True


def test_human_conflict_blocks_human_assisted_path():
    humans = [
        human("A", "A and B measure the same thing", "documentation", "doc", "h1"),
        human("B", "A and B measure distinct things", "inspection", "inspection", "h2"),
    ]
    result = EvidenceReviewEngine().review_combined(machine(), humans)
    assert result.human_review.status is HumanEvidenceStatus.CONFLICTING
    assert result.assessment_mode == "CONFLICTING_HUMAN_EVIDENCE"
    assert result.human_assisted_allowed is False


def test_machine_conflict_cannot_be_overridden_by_validated_humans():
    contradictory_machine = machine() + [Evidence(
        EvidenceCategory.CROSS_SIGNAL,
        "temperature_normal",
        "normal",
        "diagnostic_engine",
        metadata={"id": "m2", "signal": "motor_temperature", "stance": "contradicts"},
    )]
    humans = [
        human("A", "A and B measure the same thing", "documentation", "doc", "h1"),
        human("B", "A and B measure the same thing", "hardware inspection", "inspection", "h2"),
    ]
    result = EvidenceReviewEngine().review_combined(
        contradictory_machine, humans, target_claim="A and B measure the same thing"
    )
    assert result.human_review.status is HumanEvidenceStatus.VALIDATED
    assert result.machine_review.escalation_allowed is False
    assert result.human_assisted_allowed is False
    assert result.assessment_mode == "MACHINE_LIMITED"


def test_degraded_machine_evidence_cannot_be_authorized_by_human_input():
    degraded = [Evidence(
        EvidenceCategory.DEVIATION,
        "temperature_deviation",
        8,
        "baseline_engine",
        metadata={"id": "m1", "quality_status": "DEGRADED", "signal": "motor_temperature", "stance": "supports"},
    )]
    humans = [
        human("A", "A and B measure the same thing", "documentation", "doc", "h1"),
        human("B", "A and B measure the same thing", "inspection", "inspection", "h2"),
    ]
    result = EvidenceReviewEngine().review_combined(degraded, humans)
    assert result.human_assisted_allowed is False
    assert result.assessment_mode == "MACHINE_LIMITED"
