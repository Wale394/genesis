import json
import math
import unittest
from unittest.mock import patch

from genesis import Genesis
from telemetry_capability_discovery import discover_capabilities


def capability(report, name):
    return next(item for item in report["analysis_capabilities"] if item["capability"] == name)


class TelemetryCapabilityDiscoveryTests(unittest.TestCase):
    def test_full_thermal_and_battery_telemetry(self):
        report = discover_capabilities([{
            "motor_temperature": 45.0,
            "ambient_temperature": 22.0,
            "thermal_rise": 23.0,
            "battery_level": 80.0,
            "battery_voltage": 48.0,
            "battery_current": 5.0,
            "battery_temperature": 30.0,
        }])
        self.assertEqual(capability(report, "THERMAL_ANALYSIS")["status"], "AVAILABLE")
        self.assertEqual(capability(report, "BATTERY_ANALYSIS")["status"], "AVAILABLE")
        self.assertEqual(capability(report, "BATTERY_TEMPERATURE_ANALYSIS")["status"], "AVAILABLE")

    def test_thermal_only_robot(self):
        report = discover_capabilities([{"motor_temperature": 42.0}])
        self.assertEqual(report["available_telemetry"], ["motor_temperature"])
        self.assertEqual(capability(report, "THERMAL_ANALYSIS")["status"], "AVAILABLE")
        self.assertEqual(capability(report, "BATTERY_ANALYSIS")["status"], "UNAVAILABLE")

    def test_battery_only_robot(self):
        report = discover_capabilities([{
            "battery_level": 75.0,
            "battery_voltage": 48.0,
            "battery_current": 4.0,
        }])
        self.assertEqual(capability(report, "BATTERY_ANALYSIS")["status"], "AVAILABLE")
        self.assertEqual(capability(report, "THERMAL_ANALYSIS")["status"], "UNAVAILABLE")

    def test_missing_battery_temperature_is_explicit(self):
        report = discover_capabilities([{"battery_voltage": 48.0, "battery_current": 4.0}])
        self.assertIn("battery_temperature", report["missing_telemetry"])
        self.assertEqual(capability(report, "BATTERY_TEMPERATURE_ANALYSIS")["status"], "UNAVAILABLE")

    def test_voltage_without_current_reports_supported_subset_as_degraded(self):
        report = discover_capabilities([{"battery_voltage": 48.0}])
        item = capability(report, "BATTERY_ANALYSIS")
        self.assertEqual(item["status"], "DEGRADED")
        self.assertEqual(item["available_data"], ["battery_voltage"])
        self.assertEqual(item["missing_data"], ["battery_current"])

    def test_one_observation_is_thermal_available_but_pattern_insufficient(self):
        report = discover_capabilities([{"motor_temperature": 42.0}])
        self.assertEqual(capability(report, "THERMAL_ANALYSIS")["status"], "AVAILABLE")
        self.assertEqual(capability(report, "TEMPORAL_PATTERN_ANALYSIS")["status"], "INSUFFICIENT")

    def test_multiple_observations_enable_temporal_pattern_analysis(self):
        records = [{"motor_temperature": value, "ambient_temperature": 22.0}
                   for value in (42, 43, 44, 46, 48)]
        report = discover_capabilities(records)
        self.assertEqual(capability(report, "TEMPORAL_PATTERN_ANALYSIS")["status"], "AVAILABLE")

    def test_missing_and_non_finite_telemetry_are_reported_not_fabricated(self):
        report = discover_capabilities([
            {"motor_temperature": 42.0, "battery_level": math.nan},
            {"motor_temperature": None, "battery_voltage": "unknown"},
        ])
        invalid = {(item["observation_index"], item["field"])
                   for item in report["data_quality"]["invalid_measurements"]}
        self.assertIn((0, "battery_level"), invalid)
        self.assertIn((1, "battery_voltage"), invalid)
        self.assertNotIn("battery_voltage", report["available_telemetry"])
        self.assertNotIn("battery_temperature", report["available_telemetry"])

    def test_unknown_extra_fields_are_reported_without_fabricated_capability(self):
        report = discover_capabilities([{
            "motor_temperature": 42.0,
            "joint_temperature": 37.0,
            "torque": 2.0,
        }])
        self.assertEqual(report["data_quality"]["unrecognized_fields"], ["joint_temperature", "torque"])
        names = {item["capability"] for item in report["analysis_capabilities"]}
        self.assertNotIn("JOINT_TEMPERATURE_ANALYSIS", names)
        self.assertNotIn("TORQUE_ANALYSIS", names)

    def test_report_is_json_serializable(self):
        report = discover_capabilities(
            [{"robot_id": "R1", "state": "working", "motor_temperature": 42.0}],
            robot_identity={"robot_id": "R1", "manufacturer": "ABB", "robot_type": "AMR"},
        )
        decoded = json.loads(json.dumps(report, allow_nan=False))
        self.assertEqual(decoded["robot_identity"]["robot_id"], "R1")
        self.assertIn("robot_state", decoded["available_telemetry"])

    def test_adapter_source_limitations_are_preserved(self):
        report = discover_capabilities([{
            "identity": {"robot_id": "R1"},
            "telemetry": {"motor_temperature": 42.0},
            "source_metadata": {"source": "ros2"},
            "limitations": ["battery_voltage unavailable: missing unit."],
        }])
        self.assertIn(
            "battery_voltage unavailable: missing unit.",
            report["data_quality"]["source_limitations"],
        )

    def test_empty_observation_list_is_unavailable(self):
        report = discover_capabilities([])
        self.assertEqual(report["data_quality"]["status"], "UNAVAILABLE")

    def test_genesis_public_output_includes_capabilities_without_changing_decisions(self):
        records = [{
            "robot_id": "CAP-1", "manufacturer": "ABB", "robot_type": "AMR",
            "time_step": i + 1, "motor_temperature": 40.0 + i,
            "ambient_temperature": 22.0, "battery_voltage": 48.0,
            "battery_current": 4.0, "battery_level": 80.0,
        } for i in range(5)]
        with patch("genesis.discover_capabilities", return_value={"stub": True}):
            prior_output = Genesis().investigate(records)
        output = Genesis().investigate(records)
        capabilities = output.pop("capability_discovery")
        prior_output.pop("capability_discovery")
        self.assertEqual(output, prior_output)
        self.assertEqual(capabilities["observation_count"], 5)
        self.assertEqual(capability(capabilities, "TEMPORAL_PATTERN_ANALYSIS")["status"], "AVAILABLE")
        self.assertFalse(output["ml_inference"]["prediction_available"])
        self.assertIsNone(output["ml_inference"]["probability"])


if __name__ == "__main__":
    unittest.main()

