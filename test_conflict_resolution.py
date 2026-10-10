import unittest

from genesis_system.core.conflict_resolution import (
    ConflictResolutionEngine,
    ConflictResolutionStatus,
    ConflictType,
)
from genesis_system.core.evidence_contract import Evidence, EvidenceCategory
from genesis_system.core.evidence_review import EvidenceReviewEngine
from genesis_system.core.human_evidence import (
    HumanClaimType,
    HumanEvidence,
    HumanEvidenceKind,
)


def machine(name, stance, signal="relationship"):
    return Evidence(
        category=EvidenceCategory.DEVIATION,
        name=name,
        value=1,
        source=name,
        metadata={"id": name, "signal": signal, "stance": stance},
    )


def human(engineer, claim, claim_type, basis, key):
    return HumanEvidence(
        engineer_id=engineer,
        role="Engineer",
        expertise="Controls",
        claim=claim,
        claim_type=claim_type,
        basis=basis,
        kind=HumanEvidenceKind.HUMAN_EXPERT_ASSESSMENT,
        system_component="controller",
        independence_key=key,
        metadata={"id": engineer},
    )


class ConflictResolutionTests(unittest.TestCase):
    def test_no_conflict_does_not_create_conflict_case(self):
        evidence = [machine("e1", "SUPPORTS")]
        review = EvidenceReviewEngine().review(evidence)
        result = ConflictResolutionEngine().review(evidence, review)
        self.assertEqual(result.status, ConflictResolutionStatus.NO_CONFLICT)
        self.assertEqual(result.cases, [])

    def test_machine_conflict_creates_investigation_case(self):
        evidence = [machine("e1", "SUPPORTS"), machine("e2", "CONTRADICTS")]
        review = EvidenceReviewEngine().review(evidence)
        result = ConflictResolutionEngine().review(evidence, review)
        self.assertEqual(result.status, ConflictResolutionStatus.INVESTIGATION_REQUIRED)
        self.assertEqual(result.cases[0].conflict_type, ConflictType.MACHINE)
        self.assertTrue(result.investigation.required)
        self.assertTrue(result.investigation.actions)

    def test_human_disagreement_creates_human_case(self):
        evidence = [machine("e1", "SUPPORTS")]
        humans = [
            human("A", "same", HumanClaimType.SAME_INFORMATION, "inspection", "inspection-A"),
            human("B", "different", HumanClaimType.DISTINCT_INFORMATION, "documentation", "doc-B"),
        ]
        combined = EvidenceReviewEngine().review_combined(evidence, humans, target_claim="same")
        review = EvidenceReviewEngine().review(evidence)
        result = ConflictResolutionEngine().review(evidence, review, combined, humans)
        self.assertTrue(any(c.conflict_type is ConflictType.HUMAN for c in result.cases))

    def test_validated_human_evidence_does_not_erase_machine_conflict(self):
        evidence = [machine("e1", "SUPPORTS"), machine("e2", "CONTRADICTS")]
        humans = [
            human("A", "same", HumanClaimType.SAME_INFORMATION, "inspection", "inspection-A"),
            human("B", "same", HumanClaimType.SAME_INFORMATION, "documentation", "doc-B"),
        ]
        engine = EvidenceReviewEngine()
        machine_review = engine.review(evidence)
        combined = engine.review_combined(evidence, humans, target_claim="same")
        self.assertEqual(combined.human_review.status.value, "VALIDATED")
        result = ConflictResolutionEngine().review(evidence, machine_review, combined, humans)
        self.assertTrue(any(c.conflict_type is ConflictType.MACHINE_HUMAN for c in result.cases))
        self.assertEqual(result.status, ConflictResolutionStatus.INVESTIGATION_REQUIRED)


if __name__ == "__main__":
    unittest.main()
