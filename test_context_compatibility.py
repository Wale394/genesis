import unittest

from genesis_system.core.context_compatibility import (
    CompatibilityStatus,
    ContextComparison,
    ContextCompatibilityEvaluator,
    ContextRelationship,
)


class TestContextCompatibility(unittest.TestCase):
    def setUp(self):
        self.evaluator = ContextCompatibilityEvaluator()

    def test_matching_material_context_is_compatible(self):
        result = self.evaluator.assess(
            "F1",
            "C1",
            [
                ContextComparison("signal", "temperature", "temperature", ContextRelationship.SAME),
                ContextComparison("voltage", 72, 72, ContextRelationship.SAME),
                ContextComparison("motion", "stationary", "stationary", ContextRelationship.SAME),
            ],
        )
        self.assertEqual(result.status, CompatibilityStatus.COMPATIBLE)
        self.assertFalse(result.investigation_required)

    def test_known_material_difference_with_matching_context_is_partial(self):
        result = self.evaluator.assess(
            "F1",
            "C1",
            [
                ContextComparison("signal", "temperature", "temperature", ContextRelationship.SAME),
                ContextComparison("voltage", 72, 72, ContextRelationship.SAME),
                ContextComparison("motor_model", "MTR-A", "MTR-B", ContextRelationship.DIFFERENT),
            ],
        )
        self.assertEqual(result.status, CompatibilityStatus.PARTIALLY_COMPATIBLE)
        self.assertTrue(result.investigation_required)

    def test_material_unknown_overrides_known_similarity(self):
        result = self.evaluator.assess(
            "F1",
            "C1",
            [
                ContextComparison("signal", "temperature", "temperature", ContextRelationship.SAME),
                ContextComparison("operating_mode", "stationary", "stationary", ContextRelationship.SAME),
                ContextComparison("motor_model", "MTR-A", "MTR-B", ContextRelationship.DIFFERENT),
                ContextComparison("firmware", "v1", None, ContextRelationship.UNKNOWN),
                ContextComparison("maintenance", "recent", None, ContextRelationship.UNKNOWN),
            ],
        )
        self.assertEqual(result.status, CompatibilityStatus.UNKNOWN)
        self.assertTrue(result.investigation_required)

    def test_material_difference_without_matching_material_context_is_incompatible(self):
        result = self.evaluator.assess(
            "F1",
            "C1",
            [ContextComparison("motor_model", "MTR-A", "MTR-B", ContextRelationship.DIFFERENT)],
        )
        self.assertEqual(result.status, CompatibilityStatus.INCOMPATIBLE)
        self.assertFalse(result.investigation_required)

    def test_no_comparisons_is_unknown(self):
        result = self.evaluator.assess("F1", "C1", [])
        self.assertEqual(result.status, CompatibilityStatus.UNKNOWN)
        self.assertTrue(result.investigation_required)

    def test_non_material_difference_does_not_block_compatibility(self):
        result = self.evaluator.assess(
            "F1",
            "C1",
            [
                ContextComparison("signal", "temperature", "temperature", ContextRelationship.SAME),
                ContextComparison("display_label", "old", "new", ContextRelationship.DIFFERENT, material=False),
            ],
        )
        self.assertEqual(result.status, CompatibilityStatus.COMPATIBLE)
        self.assertFalse(result.investigation_required)

    def test_assessment_preserves_comparison_provenance(self):
        comparison = ContextComparison(
            "motor_model", "MTR-A", "MTR-B", ContextRelationship.DIFFERENT,
            reason="Different motor models.",
        )
        result = self.evaluator.assess("F1", "C1", [comparison])
        payload = result.to_dict()
        self.assertEqual(payload["comparisons"][0]["dimension"], "motor_model")
        self.assertEqual(payload["comparisons"][0]["relationship"], "DIFFERENT")
        self.assertEqual(payload["comparisons"][0]["reason"], "Different motor models.")


if __name__ == "__main__":
    unittest.main()
