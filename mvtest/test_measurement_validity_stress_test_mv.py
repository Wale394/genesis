import unittest

from measurement_validity_stress_test import (
    MeasurementValidity,
    assess_evidence_dependencies,
    assess_measurement_validity,
)


class MeasurementValidityStressTests(unittest.TestCase):
    def test_semantically_correct_and_calibrated_signal_is_usable(self):
        result = assess_measurement_validity(
            "motor_temperature",
            semantic_verified=True,
            calibration={"status": "VALID"},
        )
        self.assertEqual(result.validity, MeasurementValidity.VALID)
        self.assertTrue(result.usable_as_measurement_evidence)

    def test_expired_calibration_blocks_measurement_evidence(self):
        result = assess_measurement_validity(
            "motor_temperature",
            semantic_verified=True,
            calibration={"status": "EXPIRED"},
        )
        self.assertEqual(result.validity, MeasurementValidity.EXPIRED)
        self.assertFalse(result.usable_as_measurement_evidence)

    def test_failed_calibration_blocks_measurement_evidence(self):
        result = assess_measurement_validity(
            "transformer_temperature",
            semantic_verified=True,
            calibration={"status": "FAILED"},
        )
        self.assertEqual(result.validity, MeasurementValidity.FAILED)
        self.assertFalse(result.usable_as_measurement_evidence)

    def test_unknown_calibration_is_not_treated_as_valid(self):
        result = assess_measurement_validity(
            "bearing_temperature",
            semantic_verified=True,
            calibration={},
        )
        self.assertEqual(result.validity, MeasurementValidity.UNKNOWN)
        self.assertFalse(result.usable_as_measurement_evidence)

    def test_semantic_correctness_does_not_override_failed_measurement_validity(self):
        result = assess_measurement_validity(
            "motor_temperature",
            semantic_verified=True,
            calibration={"status": "FAILED"},
        )
        self.assertFalse(result.usable_as_measurement_evidence)
        self.assertIn("calibration or sensor verification has failed", result.reasons)

    def test_unverified_semantics_remain_unusable_even_with_valid_calibration(self):
        result = assess_measurement_validity(
            "motor_temperature",
            semantic_verified=False,
            calibration={"status": "VALID"},
        )
        self.assertEqual(result.validity, MeasurementValidity.VALID)
        self.assertFalse(result.usable_as_measurement_evidence)

    def test_invalid_status_does_not_become_trusted_by_default(self):
        result = assess_measurement_validity(
            "motor_temperature",
            semantic_verified=True,
            calibration={"status": "MAYBE"},
        )
        self.assertEqual(result.validity, MeasurementValidity.UNKNOWN)
        self.assertFalse(result.usable_as_measurement_evidence)

    def test_quality_scope_does_not_globally_poison_unrelated_evidence(self):
        assessments = {
            "motor_temperature": assess_measurement_validity(
                "motor_temperature",
                semantic_verified=True,
                calibration={"status": "EXPIRED"},
            ),
            "workload": assess_measurement_validity(
                "workload",
                semantic_verified=True,
                calibration={"status": "VALID"},
            ),
        }
        evidence = assess_evidence_dependencies(
            {
                "thermal_deviation": ["motor_temperature"],
                "workload_behavior": ["workload"],
                "combined_case": ["motor_temperature", "workload"],
            },
            assessments,
        )
        self.assertFalse(evidence["thermal_deviation"]["usable"])
        self.assertTrue(evidence["workload_behavior"]["usable"])
        self.assertFalse(evidence["combined_case"]["usable"])

    def test_derived_evidence_inherits_invalid_dependency(self):
        assessments = {
            "motor_temperature": assess_measurement_validity(
                "motor_temperature",
                semantic_verified=True,
                calibration={"status": "FAILED"},
            ),
            "ambient_temperature": assess_measurement_validity(
                "ambient_temperature",
                semantic_verified=True,
                calibration={"status": "VALID"},
            ),
        }
        evidence = assess_evidence_dependencies(
            {"thermal_rise": ["motor_temperature", "ambient_temperature"]},
            assessments,
        )
        self.assertFalse(evidence["thermal_rise"]["usable"])
        self.assertEqual(evidence["thermal_rise"]["affected_by"], ["motor_temperature"])


if __name__ == "__main__":
    unittest.main()
