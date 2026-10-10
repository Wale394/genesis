import unittest

from context_shift_experiment import (
    ContextDimension,
    ContextShiftEvaluator,
    ContextStatus,
    Interpretation,
)


class ContextShiftExperimentTests(unittest.TestCase):
    def setUp(self):
        self.evaluator = ContextShiftEvaluator()

    def test_normal_stable_context(self):
        result = self.evaluator.assess(
            "motor_temperature", 45, 45,
            [ContextDimension("load", 50, 50), ContextDimension("motion", "moving", "moving")],
        )
        self.assertEqual(result.interpretation, Interpretation.NORMAL)
        self.assertFalse(result.investigation_required)

    def test_deviation_with_changed_context_is_contextual(self):
        result = self.evaluator.assess(
            "motor_temperature", 60, 50,
            [ContextDimension("load", 50, 90), ContextDimension("motion", "moving", "moving")],
        )
        self.assertEqual(result.context_status, ContextStatus.CHANGED)
        self.assertEqual(result.interpretation, Interpretation.CONTEXTUAL_DEVIATION)
        self.assertFalse(result.investigation_required)

    def test_deviation_with_stable_context_is_behavioral(self):
        result = self.evaluator.assess(
            "motor_temperature", 60, 50,
            [ContextDimension("load", 50, 50), ContextDimension("motion", "moving", "moving")],
        )
        self.assertEqual(result.context_status, ContextStatus.STABLE)
        self.assertEqual(result.interpretation, Interpretation.BEHAVIORAL_DEVIATION)
        self.assertFalse(result.investigation_required)

    def test_deviation_with_unknown_context_requires_investigation(self):
        result = self.evaluator.assess(
            "motor_temperature", 60, 50,
            [ContextDimension("load", 50, None), ContextDimension("motion", "moving", "moving")],
        )
        self.assertEqual(result.context_status, ContextStatus.UNKNOWN)
        self.assertEqual(result.interpretation, Interpretation.INSUFFICIENT_CONTEXT)
        self.assertTrue(result.investigation_required)
        self.assertIn("material operating context is unknown", result.reason)

    def test_unknown_context_is_not_treated_as_stable(self):
        result = self.evaluator.assess(
            "motor_temperature", 60, 50,
            [ContextDimension("load", None, 80)],
        )
        self.assertNotEqual(result.context_status, ContextStatus.STABLE)
        self.assertNotEqual(result.interpretation, Interpretation.BEHAVIORAL_DEVIATION)

    def test_non_material_context_unknown_does_not_block_interpretation(self):
        result = self.evaluator.assess(
            "motor_temperature", 60, 50,
            [ContextDimension("load", 50, 50), ContextDimension("weather", None, None, material=False)],
        )
        self.assertEqual(result.context_status, ContextStatus.STABLE)
        self.assertEqual(result.interpretation, Interpretation.BEHAVIORAL_DEVIATION)

    def test_empty_context_is_conservative(self):
        result = self.evaluator.assess("motor_temperature", 60, 50, [])
        self.assertEqual(result.context_status, ContextStatus.STABLE)
        self.assertEqual(result.interpretation, Interpretation.BEHAVIORAL_DEVIATION)


if __name__ == "__main__":
    unittest.main()
