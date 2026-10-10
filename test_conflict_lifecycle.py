import unittest

from genesis_system.core.conflict_lifecycle import (
    ConflictLifecycleEngine,
    ConflictLifecycleStatus,
    ConflictRecord,
)
from genesis_system.core.conflict_resolution import (
    ConflictCase,
    ConflictResolutionStatus,
    ConflictType,
)
from genesis_system.core.evidence_contract import Evidence, EvidenceCategory
from genesis_system.core.investigation_memory import (
    InvestigationFinding,
    InvestigationFindingStatus,
    InvestigationOutcome,
)


class ConflictLifecycleTests(unittest.TestCase):
    def setUp(self):
        case = ConflictCase(
            conflict_id="machine-human-conflict-001",
            conflict_type=ConflictType.MACHINE_HUMAN,
            subject="sensor_relationship",
            supporting_refs=["human-1"],
            contradicting_refs=["machine-2"],
            reason="Machine and human evidence disagree.",
            status=ConflictResolutionStatus.INVESTIGATION_REQUIRED,
        )
        self.record = ConflictRecord(conflict=case, opened_at="2026-10-06T12:00:00Z")
        self.engine = ConflictLifecycleEngine()

    def test_validated_finding_resolves_conflict(self):
        outcome = InvestigationOutcome(
            investigation_id="INV-001",
            status="COMPLETED",
            findings=[InvestigationFinding(
                finding_id="F-001",
                statement="Sensors share the same physical measurement path.",
                status=InvestigationFindingStatus.VALIDATED,
                evidence_refs=["machine-human-conflict-001"],
            )],
        )
        update = self.engine.apply_investigation(self.record, outcome)
        self.assertEqual(update.status, ConflictLifecycleStatus.RESOLVED)

    def test_refuted_finding_marks_conflict_refuted(self):
        outcome = InvestigationOutcome(
            investigation_id="INV-002",
            status="COMPLETED",
            findings=[InvestigationFinding(
                finding_id="F-002",
                statement="The contested relationship is not present.",
                status=InvestigationFindingStatus.REFUTED,
                context={"conflict_id": "machine-human-conflict-001"},
            )],
        )
        update = self.engine.apply_investigation(self.record, outcome)
        self.assertEqual(update.status, ConflictLifecycleStatus.REFUTED)

    def test_no_decisive_finding_remains_uncertain(self):
        outcome = InvestigationOutcome(
            investigation_id="INV-003",
            status="INCOMPLETE",
            findings=[],
            new_evidence=[Evidence(
                category=EvidenceCategory.OBSERVATION,
                name="fresh_observation",
                value=42,
                source="sensor-A",
                metadata={"id": "OBS-9"},
            )],
        )
        update = self.engine.apply_investigation(self.record, outcome)
        self.assertEqual(update.status, ConflictLifecycleStatus.STILL_UNCERTAIN)
        self.assertEqual(update.new_evidence_refs, ["OBS-9"])

    def test_original_conflict_is_preserved(self):
        original = self.record.to_dict()
        outcome = InvestigationOutcome(
            investigation_id="INV-004",
            status="COMPLETED",
            findings=[InvestigationFinding(
                finding_id="F-004",
                statement="Resolved.",
                status=InvestigationFindingStatus.VALIDATED,
                context={"conflict_id": "machine-human-conflict-001"},
            )],
        )
        self.engine.apply_investigation(self.record, outcome)
        self.assertEqual(self.record.to_dict(), original)
        self.assertEqual(self.record.conflict.reason, "Machine and human evidence disagree.")

    def test_contradictory_investigation_results_remain_uncertain(self):
        outcome = InvestigationOutcome(
            investigation_id="INV-005",
            status="COMPLETED",
            findings=[
                InvestigationFinding(
                    finding_id="F-005A",
                    statement="Claim supported.",
                    status=InvestigationFindingStatus.VALIDATED,
                    context={"conflict_id": "machine-human-conflict-001"},
                ),
                InvestigationFinding(
                    finding_id="F-005B",
                    statement="Claim refuted.",
                    status=InvestigationFindingStatus.REFUTED,
                    context={"conflict_id": "machine-human-conflict-001"},
                ),
            ],
        )
        update = self.engine.apply_investigation(self.record, outcome)
        self.assertEqual(update.status, ConflictLifecycleStatus.STILL_UNCERTAIN)


if __name__ == "__main__":
    unittest.main()
