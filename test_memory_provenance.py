import unittest

from genesis_system.core.investigation_memory import InvestigationFinding, InvestigationFindingStatus, InvestigationOutcome
from genesis_system.core.memory_provenance import MemoryProvenance, ProvenanceStatus, MemoryReuseStance
from genesis_system.core.reliability_memory import ReliabilityMemory
from genesis_system.core.reliability_memory_retrieval import MemoryQuery, ReliabilityMemoryRetriever


class TestMemoryProvenance(unittest.TestCase):
    def test_complete_provenance_supports_reuse(self):
        provenance = MemoryProvenance(
            source="INV-1",
            evidence_refs=["E1"],
            validation_refs=["VAL-1"],
            contributor_refs=["ENG-A"],
        )
        self.assertEqual(provenance.status(), ProvenanceStatus.COMPLETE)
        memory = ReliabilityMemory()
        memory.store_investigation(InvestigationOutcome(
            investigation_id="INV-1", status="COMPLETED",
            findings=[InvestigationFinding(
                finding_id="F1", statement="A", status=InvestigationFindingStatus.VALIDATED,
                context={"robot_type": "AMR"}, evidence_refs=["E1"], provenance=provenance.to_dict(),
            )],
        ))
        result = ReliabilityMemoryRetriever(memory).retrieve(MemoryQuery(robot_type="AMR"))
        finding = result["validated_findings"][0]
        self.assertEqual(finding["reuse_stance"], MemoryReuseStance.SUPPORT.value)
        self.assertEqual(finding["provenance_status"], "COMPLETE")

    def test_validated_without_complete_provenance_is_caution(self):
        memory = ReliabilityMemory()
        memory.store_investigation(InvestigationOutcome(
            investigation_id="INV-1", status="COMPLETED",
            findings=[InvestigationFinding(
                finding_id="F1", statement="A", status=InvestigationFindingStatus.VALIDATED,
                context={"robot_type": "AMR"}, evidence_refs=["E1"],
            )],
        ))
        finding = ReliabilityMemoryRetriever(memory).retrieve(MemoryQuery(robot_type="AMR"))["validated_findings"][0]
        self.assertEqual(finding["reuse_stance"], MemoryReuseStance.CAUTION.value)

    def test_refuted_memory_is_excluded_from_support(self):
        memory = ReliabilityMemory()
        memory.store_investigation(InvestigationOutcome(
            investigation_id="INV-1", status="COMPLETED",
            findings=[InvestigationFinding(
                finding_id="F1", statement="A", status=InvestigationFindingStatus.REFUTED,
                context={"robot_type": "AMR"}, evidence_refs=["E1"],
            )],
        ))
        finding = ReliabilityMemoryRetriever(memory).retrieve(MemoryQuery(robot_type="AMR"))["refuted_findings"][0]
        self.assertEqual(finding["reuse_stance"], MemoryReuseStance.EXCLUDE.value)

    def test_hypothesis_with_provenance_remains_caution(self):
        provenance = MemoryProvenance(source="INV-1", evidence_refs=["E1"], validation_refs=["VAL-1"])
        memory = ReliabilityMemory()
        memory.store_investigation(InvestigationOutcome(
            investigation_id="INV-1", status="COMPLETED",
            findings=[InvestigationFinding(
                finding_id="F1", statement="A", status=InvestigationFindingStatus.HYPOTHESIS,
                context={"robot_type": "AMR"}, evidence_refs=["E1"], provenance=provenance.to_dict(),
            )],
        ))
        finding = ReliabilityMemoryRetriever(memory).retrieve(MemoryQuery(robot_type="AMR"))["unresolved_findings"][0]
        self.assertEqual(finding["reuse_stance"], MemoryReuseStance.CAUTION.value)

    def test_provenance_is_preserved_in_serialized_finding(self):
        provenance = MemoryProvenance(source="INV-1", evidence_refs=["E1"], validation_refs=["VAL-1"], contributor_refs=["ENG-A"])
        finding = InvestigationFinding(
            finding_id="F1", statement="A", status=InvestigationFindingStatus.VALIDATED,
            provenance=provenance.to_dict(),
        )
        self.assertEqual(finding.to_dict()["provenance"]["source"], "INV-1")
        self.assertEqual(finding.to_dict()["provenance"]["contributor_refs"], ["ENG-A"])


if __name__ == "__main__":
    unittest.main()
