import pytest

from genesis_system.core.human_evidence import (
    HumanClaimType,
    HumanEvidence,
    HumanEvidenceKind,
    HumanEvidenceReviewEngine,
    HumanEvidenceStatus,
)


def make_evidence(**overrides):
    values = {
        "engineer_id": "ENG-001",
        "role": "Controls Engineer",
        "expertise": "Motor systems",
        "claim": "Sensor A and Sensor B measure the same physical phenomenon.",
        "claim_type": HumanClaimType.SAME_INFORMATION,
        "basis": "Manufacturer wiring documentation",
        "kind": HumanEvidenceKind.HUMAN_DOCUMENTATION,
        "system_component": "motor-controller-A",
        "independence_key": "manufacturer-doc-27",
        "metadata": {"id": "h1"},
    }
    values.update(overrides)
    return HumanEvidence(**values)


def test_human_evidence_requires_identity_and_basis():
    with pytest.raises(ValueError, match="engineer_id"):
        make_evidence(engineer_id="")

    with pytest.raises(ValueError, match="basis"):
        make_evidence(basis="")


def test_confidence_must_be_between_zero_and_one():
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        make_evidence(confidence=1.1)


def test_human_evidence_serializes_without_losing_provenance():
    evidence = make_evidence(
        supporting_evidence=["SCHEMATIC-102"],
        provenance={"source": "engineering-review"},
        confidence=0.9,
    )

    result = evidence.to_dict()

    assert result["engineer_id"] == "ENG-001"
    assert result["claim_type"] == "same_information"
    assert result["supporting_evidence"] == ["SCHEMATIC-102"]
    assert result["provenance"]["source"] == "engineering-review"


def test_one_engineer_does_not_validate_a_high_stakes_relationship():
    evidence = [make_evidence()]

    review = HumanEvidenceReviewEngine().review(evidence)

    assert review.status is HumanEvidenceStatus.CORROBORATED
    assert review.supporting_refs == ["h1"]


def test_two_engineers_with_same_basis_do_not_count_as_independent():
    evidence = [
        make_evidence(metadata={"id": "h1"}, engineer_id="ENG-001"),
        make_evidence(metadata={"id": "h2"}, engineer_id="ENG-002"),
    ]

    review = HumanEvidenceReviewEngine().review(evidence)

    assert review.status is HumanEvidenceStatus.CORROBORATED
    assert review.independent_support_groups == ["manufacturer-doc-27"]


def test_two_independent_bases_can_validate_a_claim():
    evidence = [
        make_evidence(metadata={"id": "h1"}, independence_key="manufacturer-doc-27"),
        make_evidence(
            metadata={"id": "h2"},
            engineer_id="ENG-002",
            basis="Independent hardware inspection",
            kind=HumanEvidenceKind.HUMAN_OBSERVATION,
            independence_key="hardware-inspection-014",
        ),
    ]

    review = HumanEvidenceReviewEngine().review(evidence)

    assert review.status is HumanEvidenceStatus.VALIDATED
    assert len(review.independent_support_groups) == 2


def test_disagreement_remains_visible_and_blocks_validation():
    evidence = [
        make_evidence(metadata={"id": "h1"}),
        make_evidence(
            metadata={"id": "h2"},
            engineer_id="ENG-002",
            claim="Sensor A and Sensor B measure distinct physical phenomena.",
            claim_type=HumanClaimType.DISTINCT_INFORMATION,
            basis="Independent hardware inspection",
            kind=HumanEvidenceKind.HUMAN_OBSERVATION,
            independence_key="hardware-inspection-014",
        ),
    ]

    review = HumanEvidenceReviewEngine().review(evidence)

    assert review.status is HumanEvidenceStatus.CONFLICTING
    assert review.supporting_refs == ["h1"]
    assert review.contradicting_refs == ["h2"]


def test_machine_only_and_human_assisted_paths_can_remain_distinct():
    evidence = make_evidence()
    machine_assessment = {"source": "genesis_only", "relationship": "UNKNOWN"}
    human_review = HumanEvidenceReviewEngine().review([evidence])

    assert machine_assessment["relationship"] == "UNKNOWN"
    assert human_review.status is HumanEvidenceStatus.CORROBORATED
