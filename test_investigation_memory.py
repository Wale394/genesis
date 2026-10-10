import unittest

from genesis_system.core.investigation_memory import (
    InvestigationFinding,
    InvestigationFindingStatus,
    InvestigationOutcome,
)
from genesis_system.core.reliability_memory import ReliabilityMemory


class TestInvestigationMemory(unittest.TestCase):
    def test_finding_requires_explicit_status(self):
        finding = InvestigationFinding(
            finding_id="F001",
            statement="Temperature rise is context-dependent.",
            status=InvestigationFindingStatus.HYPOTHESIS,
            evidence_refs=["evidence-001"],
        )
        self.assertEqual(finding.to_dict()["status"], "HYPOTHESIS")

    def test_only_validated_findings_are_returned_as_validated(self):
        outcome = InvestigationOutcome(
            investigation_id="INV001",
            status="COMPLETED",
            findings=[
                InvestigationFinding(
                    finding_id="F001",
                    statement="Observed repeated temperature deviation.",
                    status=InvestigationFindingStatus.OBSERVED,
                ),
                InvestigationFinding(
                    finding_id="F002",
                    statement="Context explains the deviation.",
                    status=InvestigationFindingStatus.VALIDATED,
                ),
            ],
        )
        self.assertEqual([f.finding_id for f in outcome.validated_findings], ["F002"])

    def test_memory_preserves_hypothesis_without_promoting_it(self):
        memory = ReliabilityMemory()
        outcome = InvestigationOutcome(
            investigation_id="INV001",
            status="COMPLETED",
            findings=[
                InvestigationFinding(
                    finding_id="F001",
                    statement="Possible sensor artifact.",
                    status=InvestigationFindingStatus.HYPOTHESIS,
                )
            ],
        )
        memory.store_investigation(outcome)
        self.assertEqual(len(memory.investigations()), 1)
        self.assertEqual(memory.validated_findings(), [])
        self.assertEqual(
            memory.investigations()[0]["investigation"]["findings"][0]["status"],
            "HYPOTHESIS",
        )


    def test_investigation_memory_round_trips_through_entries(self):
        memory = ReliabilityMemory()
        outcome = InvestigationOutcome(
            investigation_id="INV-ROUNDTRIP",
            status="COMPLETED",
            findings=[
                InvestigationFinding(
                    finding_id="F-ROUNDTRIP",
                    statement="A stored investigation can be restored.",
                    status=InvestigationFindingStatus.VALIDATED,
                    context={"motion": "stationary"},
                )
            ],
        )
        memory.store_investigation(outcome)

        restored = ReliabilityMemory(memory.entries)

        self.assertEqual(len(restored.investigations()), 1)
        self.assertEqual(
            restored.investigations()[0]["investigation"]["investigation_id"],
            "INV-ROUNDTRIP",
        )
        self.assertEqual(len(restored.validated_findings()), 1)

    def test_validated_finding_can_be_reused_later(self):
        memory = ReliabilityMemory()
        outcome = InvestigationOutcome(
            investigation_id="INV002",
            status="COMPLETED",
            findings=[
                InvestigationFinding(
                    finding_id="F002",
                    statement="Deviation is normal in this operating context.",
                    status=InvestigationFindingStatus.VALIDATED,
                    evidence_refs=["evidence-007", "evidence-008"],
                    context={"motion_state": "stationary"},
                )
            ],
        )
        memory.store_investigation(outcome)
        findings = memory.validated_findings()
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["finding_id"], "F002")
        self.assertEqual(findings[0]["context"]["motion_state"], "stationary")


if __name__ == "__main__":
    unittest.main()
