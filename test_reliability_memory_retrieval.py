import unittest

from genesis_system.core.investigation_memory import (
    InvestigationFinding,
    InvestigationFindingStatus,
    InvestigationOutcome,
)
from genesis_system.core.reliability_memory import ReliabilityMemory
from genesis_system.core.reliability_memory_retrieval import MemoryQuery, ReliabilityMemoryRetriever


class TestReliabilityMemoryRetrieval(unittest.TestCase):
    def setUp(self):
        self.memory = ReliabilityMemory()
        self.retriever = ReliabilityMemoryRetriever(self.memory)

    def _store(self, investigation_id, finding_id, status, context):
        self.memory.store_investigation(InvestigationOutcome(
            investigation_id=investigation_id,
            status="COMPLETED",
            findings=[InvestigationFinding(
                finding_id=finding_id,
                statement=f"Finding {finding_id}",
                status=status,
                context=context,
                evidence_refs=[f"e-{finding_id}"],
            )],
        ))

    def test_empty_memory_is_unavailable(self):
        result = self.retriever.retrieve(MemoryQuery(robot_type="AMR"))
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["match_count"], 0)

    def test_validated_finding_is_retrieved_by_explicit_context(self):
        self._store("INV1", "F1", InvestigationFindingStatus.VALIDATED, {"robot_type": "AMR", "motion": "stationary"})
        result = self.retriever.retrieve(MemoryQuery(robot_type="AMR", context={"motion": "stationary"}))
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertEqual(result["validated_count"], 1)
        self.assertEqual(result["validated_findings"][0]["finding_id"], "F1")

    def test_hypothesis_is_not_returned_as_validated(self):
        self._store("INV1", "F1", InvestigationFindingStatus.HYPOTHESIS, {"robot_type": "AMR"})
        result = self.retriever.retrieve(MemoryQuery(robot_type="AMR"))
        self.assertEqual(result["validated_count"], 0)
        self.assertEqual(result["unresolved_count"], 1)
        self.assertEqual(result["unresolved_findings"][0]["status"], "HYPOTHESIS")

    def test_refuted_finding_is_retrieved_as_refuted(self):
        self._store("INV1", "F1", InvestigationFindingStatus.REFUTED, {"robot_type": "AMR"})
        result = self.retriever.retrieve(MemoryQuery(robot_type="AMR"))
        self.assertEqual(result["refuted_count"], 1)
        self.assertEqual(result["validated_count"], 0)

    def test_conflicting_historical_findings_are_not_resolved_by_voting(self):
        context = {"robot_type": "AMR", "motion": "stationary"}
        self._store("INV1", "F1", InvestigationFindingStatus.VALIDATED, context)
        self._store("INV2", "F2", InvestigationFindingStatus.REFUTED, context)
        result = self.retriever.retrieve(MemoryQuery(robot_type="AMR", context={"motion": "stationary"}))
        self.assertEqual(result["status"], "CONFLICTING")
        self.assertEqual(len(result["conflicts"]), 1)
        self.assertIn("conflicting findings", result["limitations"][0].lower() + result["limitations"][-1].lower())


if __name__ == "__main__":
    unittest.main()
