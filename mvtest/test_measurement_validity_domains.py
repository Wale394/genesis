import unittest

from measurement_validity_stress_test import (
    MeasurementValidity,
    assess_evidence_dependencies,
    assess_measurement_validity,
)


class CrossDomainMeasurementValidityTests(unittest.TestCase):
    def test_robotics_sensor_failure_is_scoped(self):
        assessments = {
            "motor_temperature": assess_measurement_validity(
                "motor_temperature", semantic_verified=True,
                calibration={"status": "FAILED"}),
            "workload": assess_measurement_validity(
                "workload", semantic_verified=True,
                calibration={"status": "VALID"}),
        }
        result = assess_evidence_dependencies(
            {"thermal_deviation": ["motor_temperature"],
             "workload_behavior": ["workload"]}, assessments)
        self.assertFalse(result["thermal_deviation"]["usable"])
        self.assertTrue(result["workload_behavior"]["usable"])

    def test_energy_infrastructure_sensor_failure_is_scoped(self):
        assessments = {
            "transformer_temperature": assess_measurement_validity(
                "transformer_temperature", semantic_verified=True,
                calibration={"status": "EXPIRED"}),
            "line_current": assess_measurement_validity(
                "line_current", semantic_verified=True,
                calibration={"status": "VALID"}),
        }
        result = assess_evidence_dependencies(
            {"thermal_stress": ["transformer_temperature"],
             "load_behavior": ["line_current"]}, assessments)
        self.assertFalse(result["thermal_stress"]["usable"])
        self.assertTrue(result["load_behavior"]["usable"])

    def test_industrial_equipment_sensor_failure_is_scoped(self):
        assessments = {
            "spindle_vibration": assess_measurement_validity(
                "spindle_vibration", semantic_verified=True,
                calibration={"status": "FAILED"}),
            "production_rate": assess_measurement_validity(
                "production_rate", semantic_verified=True,
                calibration={"status": "VALID"}),
        }
        result = assess_evidence_dependencies(
            {"vibration_anomaly": ["spindle_vibration"],
             "throughput_behavior": ["production_rate"]}, assessments)
        self.assertFalse(result["vibration_anomaly"]["usable"])
        self.assertTrue(result["throughput_behavior"]["usable"])

    def test_unknown_validity_is_conservative_across_domains(self):
        signals = [
            ("motor_temperature", "robotics"),
            ("transformer_temperature", "energy"),
            ("spindle_vibration", "industrial"),
        ]
        for signal, _domain in signals:
            result = assess_measurement_validity(
                signal, semantic_verified=True, calibration={})
            self.assertEqual(result.validity, MeasurementValidity.UNKNOWN)
            self.assertFalse(result.usable_as_measurement_evidence)

    def test_validity_is_not_domain_specific(self):
        cases = [
            ("motor_temperature", "VALID"),
            ("transformer_temperature", "VALID"),
            ("spindle_vibration", "VALID"),
        ]
        for signal, status in cases:
            result = assess_measurement_validity(
                signal, semantic_verified=True,
                calibration={"status": status})
            self.assertTrue(result.usable_as_measurement_evidence)

    def test_mixed_evidence_requires_all_dependencies_to_be_usable(self):
        assessments = {
            "transformer_temperature": assess_measurement_validity(
                "transformer_temperature", semantic_verified=True,
                calibration={"status": "VALID"}),
            "line_current": assess_measurement_validity(
                "line_current", semantic_verified=True,
                calibration={"status": "FAILED"}),
        }
        result = assess_evidence_dependencies(
            {"thermal_load_relationship": [
                "transformer_temperature", "line_current"]},
            assessments)
        self.assertFalse(result["thermal_load_relationship"]["usable"])
        self.assertEqual(result["thermal_load_relationship"]["affected_by"], ["line_current"])


if __name__ == "__main__":
    unittest.main()
