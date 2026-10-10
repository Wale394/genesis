import unittest

from semantic_boundary_guard import SemanticStatus, assess_observation_semantics


class SemanticBoundaryGuardTests(unittest.TestCase):
    def test_verified_signal_can_be_used_as_physical_evidence(self):
        result = assess_observation_semantics(
            ["motor_temperature"],
            {"signals": {"motor_temperature": {
                "canonical_field": "motor_temperature",
                "source_field": "motor_temp_c",
                "physical_quantity": "temperature",
                "unit": "C",
                "transform": "identity",
            }}},
        )
        self.assertEqual(result["motor_temperature"].status, SemanticStatus.VERIFIED)
        self.assertTrue(result["motor_temperature"].usable_as_physical_evidence)

    def test_missing_semantics_cannot_be_treated_as_verified(self):
        result = assess_observation_semantics(
            ["motor_temperature"],
            {"signals": {"motor_temperature": {"canonical_field": "motor_temperature"}}},
        )
        self.assertNotEqual(result["motor_temperature"].status, SemanticStatus.VERIFIED)
        self.assertFalse(result["motor_temperature"].usable_as_physical_evidence)

    def test_wrong_mapping_is_not_hidden_by_a_numeric_value(self):
        result = assess_observation_semantics(
            ["motor_temperature"],
            {"signals": {"motor_temperature": {
                "canonical_field": "motor_temperature",
                "source_field": "motor_load",
                "physical_quantity": "load",
                "unit": "%",
                "transform": "identity",
            }}},
        )
        self.assertFalse(result["motor_temperature"].usable_as_physical_evidence)
        self.assertIn("physical quantity conflicts with canonical signal", result["motor_temperature"].reasons)


if __name__ == "__main__":
    unittest.main()
