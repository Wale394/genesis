import unittest

from genesis_system.core.closed_loop import ClosedLoopReliabilityEngine
from genesis_system.core.evidence_contract import Evidence, EvidenceCategory
from genesis_system.core.investigation_memory import (
    InvestigationFinding,
    InvestigationFindingStatus,
    InvestigationOutcome,
)
from genesis_system.core.reliability_state import ReliabilityLevel


class TestClosedLoopReliabilityEngine(unittest.TestCase):
    def test_conflict_keeps_state_at_observation_and_requests_investigation(self):
        evidence = [
            Evidence(
                category=EvidenceCategory.DEVIATION,
                name="temperature_high",
                value=8,
                source="temperature",
                metadata={"id": "e1", "signal": "motor_temperature", "stance": "SUPPORTS"},
            ),
            Evidence(
                category=EvidenceCategory.CROSS_SIGNAL,
                name="diagnostic_normal",
                value="normal",
                source="diagnostic",
                metadata={"id": "e2", "signal": "motor_temperature", "stance": "CONTRADICTS"},
            ),
        ]
        result = ClosedLoopReliabilityEngine().assess(evidence)
        self.assertEqual(result.state.level, ReliabilityLevel.OBSERVATION)
        self.assertTrue(result.investigation.required)
        self.assertFalse(result.memory_recorded)

    def test_investigation_outcome_is_stored_for_later_review(self):
        engine = ClosedLoopReliabilityEngine()
        evidence = [
            Evidence(
                category=EvidenceCategory.DEVIATION,
                name="temperature_high",
                value=8,
                source="temperature",
                metadata={"id": "e1"},
            )
        ]
        outcome = InvestigationOutcome(
            investigation_id="INV001",
            status="COMPLETED",
            findings=[
                InvestigationFinding(
                    finding_id="F001",
                    statement="Deviation is normal in stationary operation.",
                    status=InvestigationFindingStatus.VALIDATED,
                    evidence_refs=["e1", "e2"],
                )
            ],
        )
        result = engine.assess(evidence, investigation_outcome=outcome)
        self.assertTrue(result.memory_recorded)
        self.assertEqual(len(engine.memory.validated_findings()), 1)
        self.assertEqual(result.metadata["validated_finding_count"], 1)

    def test_hypothesis_is_not_treated_as_validated_memory(self):
        engine = ClosedLoopReliabilityEngine()
        outcome = InvestigationOutcome(
            investigation_id="INV002",
            status="COMPLETED",
            findings=[
                InvestigationFinding(
                    finding_id="F002",
                    statement="Possible sensor artifact.",
                    status=InvestigationFindingStatus.HYPOTHESIS,
                )
            ],
        )
        result = engine.assess([], investigation_outcome=outcome)
        self.assertTrue(result.memory_recorded)
        self.assertEqual(result.metadata["validated_finding_count"], 0)

    def test_close_investigation_reassesses_with_new_evidence(self):
        engine = ClosedLoopReliabilityEngine()
        prior = [
            Evidence(
                category=EvidenceCategory.DEVIATION,
                name="temperature_high",
                value=8,
                source="temperature",
                metadata={"id": "e1"},
            )
        ]
        outcome = InvestigationOutcome(
            investigation_id="INV003",
            status="COMPLETED",
            new_evidence=[
                Evidence(
                    category=EvidenceCategory.TEMPORAL,
                    name="persistent_deviation",
                    value=12,
                    source="history",
                    metadata={"id": "e2"},
                ),
                Evidence(
                    category=EvidenceCategory.CONTEXT,
                    name="repeated_context",
                    value=True,
                    source="context_engine",
                    metadata={"id": "e3"},
                ),
            ],
            findings=[
                InvestigationFinding(
                    finding_id="F003",
                    statement="Deviation repeats in the same operating context.",
                    status=InvestigationFindingStatus.VALIDATED,
                    evidence_refs=["e1", "e2", "e3"],
                )
            ],
        )
        result = engine.close_investigation(prior, outcome)
        self.assertEqual(result.state.level, ReliabilityLevel.CRITICAL)
        self.assertTrue(result.metadata["reassessment"])
        self.assertEqual(result.metadata["investigation_id"], "INV003")
        self.assertEqual(len(engine.memory.validated_findings()), 1)


if __name__ == "__main__":
    unittest.main()
