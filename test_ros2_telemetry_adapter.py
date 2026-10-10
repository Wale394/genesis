import importlib.util
import json
import sys
import unittest
from types import SimpleNamespace

from genesis import Genesis
from ros2_telemetry_adapter import ROS2TelemetryAdapter


def kv(key, value):
    return {"key": key, "value": value}


def diagnostic_array(*statuses, stamp=None):
    header = {"stamp": stamp} if stamp is not None else {}
    return {"header": header, "status": list(statuses)}


def status(name, *values):
    return {"name": name, "values": list(values)}


class ROS2TelemetryAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = ROS2TelemetryAdapter(
            "R-ROS-1", manufacturer="ABB", robot_type="AMR"
        )

    def test_valid_ros_like_input_becomes_genesis_snapshot(self):
        message = diagnostic_array(
            status("motor_controller",
                   kv("motor_temperature", "42.5 C"),
                   kv("ambient_temperature", "20 Celsius"),
                   kv("robot_state", "active")),
            stamp={"sec": 100, "nanosec": 250_000_000},
        )
        record = self.adapter.adapt(message)
        self.assertEqual(record["identity"], {
            "robot_id": "R-ROS-1", "manufacturer": "ABB", "robot_type": "AMR",
        })
        self.assertEqual(record["telemetry"]["motor_temperature"], 42.5)
        self.assertEqual(record["telemetry"]["ambient_temperature"], 20.0)
        self.assertEqual(record["telemetry"]["robot_state"], "working")
        self.assertEqual(record["source"], "ros2")

    def test_battery_diagnostics_map_to_canonical_fields(self):
        record = self.adapter.adapt(diagnostic_array(status(
            "battery",
            kv("battery_level", "85"), kv("battery_level_unit", "percent"),
            kv("battery_voltage", "48.2 V"),
            kv("battery_current", "12.5 A"),
            kv("battery_temperature", "31 C"),
        )))
        self.assertEqual(record["telemetry"]["battery_level"], 85.0)
        self.assertEqual(record["telemetry"]["battery_voltage"], 48.2)
        self.assertEqual(record["telemetry"]["battery_current"], 12.5)
        self.assertEqual(record["telemetry"]["battery_temperature"], 31.0)

    def test_thermal_diagnostics_normalize_explicit_units(self):
        record = self.adapter.adapt(diagnostic_array(status(
            "thermal",
            kv("motor_temperature", "104 F"),
            kv("ambient_temperature", "293.15 K"),
        )))
        self.assertAlmostEqual(record["telemetry"]["motor_temperature"], 40.0)
        self.assertAlmostEqual(record["telemetry"]["ambient_temperature"], 20.0)
        self.assertEqual(record["source_metadata"]["units"]["motor_temperature"], "C")

    def test_multiple_diagnostic_statuses_merge(self):
        record = self.adapter.adapt(diagnostic_array(
            status("thermal", kv("motor_temperature", "40 C")),
            status("battery", kv("battery_voltage", "48 V")),
            status("power", kv("power_consumption", "600 W")),
        ))
        self.assertEqual(record["telemetry"]["motor_temperature"], 40.0)
        self.assertEqual(record["telemetry"]["battery_voltage"], 48.0)
        self.assertEqual(record["telemetry"]["power_consumption"], 600.0)
        self.assertEqual(record["source_metadata"]["diagnostic_components"], ["thermal", "battery", "power"])

    def test_unknown_keys_are_ignored_and_reported(self):
        record = self.adapter.adapt(diagnostic_array(status(
            "vendor", kv("mystery_sensor", "123"), kv("motor_temperature", "40 C")
        )))
        self.assertNotIn("mystery_sensor", record["telemetry"])
        self.assertEqual(record["source_metadata"]["ignored_keys"], ["mystery_sensor"])
        self.assertTrue(any("Unmapped diagnostic keys" in item for item in record["limitations"]))

    def test_missing_optional_values_remain_absent(self):
        record = self.adapter.adapt(diagnostic_array(status(
            "battery", kv("battery_voltage", "48 V")
        )))
        self.assertIn("battery_voltage", record["telemetry"])
        self.assertNotIn("battery_level", record["telemetry"])
        self.assertNotIn("motor_temperature", record["telemetry"])

    def test_malformed_numeric_value_is_not_telemetry(self):
        record = self.adapter.adapt(diagnostic_array(status(
            "battery", kv("battery_voltage", "not-a-number V")
        )))
        self.assertNotIn("battery_voltage", record["telemetry"])
        self.assertTrue(any("malformed numeric value" in item for item in record["limitations"]))

    def test_units_are_required_or_explicitly_configured(self):
        message = diagnostic_array(status("battery", kv("battery_voltage", "48.0")))
        unsupported = self.adapter.adapt(message)
        self.assertNotIn("battery_voltage", unsupported["telemetry"])
        self.assertTrue(any("missing or unsupported unit" in item for item in unsupported["limitations"]))

        configured = ROS2TelemetryAdapter(
            "R-ROS-1", field_units={"battery_voltage": "volts"}
        ).adapt(message)
        self.assertEqual(configured["telemetry"]["battery_voltage"], 48.0)

    def test_identity_is_preserved_and_required_robot_id_is_enforced(self):
        self.assertEqual(self.adapter.adapt(diagnostic_array())["identity"]["robot_id"], "R-ROS-1")
        with self.assertRaisesRegex(ValueError, "robot_id is required"):
            ROS2TelemetryAdapter(None)

    def test_ros_timestamp_is_preserved_and_used_as_time_step(self):
        record = self.adapter.adapt(diagnostic_array(
            status("battery", kv("battery_voltage", "48 V")),
            stamp=SimpleNamespace(sec=12, nanosec=500_000_000),
        ))
        self.assertEqual(record["telemetry"]["time_step"], 12.5)
        self.assertEqual(record["source_metadata"]["timestamp"], {
            "sec": 12, "nanosec": 500_000_000,
        })

    def test_explicit_time_step_overrides_timestamp_for_genesis_ordering(self):
        record = self.adapter.adapt(
            diagnostic_array(stamp={"sec": 12, "nanosec": 500_000_000}),
            time_step=7,
        )
        self.assertEqual(record["telemetry"]["time_step"], 7)
        self.assertEqual(record["source_metadata"]["timestamp"]["sec"], 12)

    def test_conflicting_duplicate_keys_are_left_unavailable(self):
        record = self.adapter.adapt(diagnostic_array(
            status("battery_a", kv("battery_voltage", "48 V")),
            status("battery_b", kv("battery_voltage", "49 V")),
        ))
        self.assertNotIn("battery_voltage", record["telemetry"])
        self.assertTrue(any("conflicting duplicate" in item for item in record["limitations"]))

    def test_identical_duplicate_keys_are_merged_deterministically(self):
        record = self.adapter.adapt(diagnostic_array(
            status("battery_a", kv("battery_voltage", "48 V")),
            status("battery_b", kv("battery_voltage", "48.0 volts")),
        ))
        self.assertEqual(record["telemetry"]["battery_voltage"], 48.0)
        self.assertEqual(record["source_metadata"]["source_keys"]["battery_voltage"], ["battery_voltage"])

    def test_partial_and_empty_diagnostic_arrays_do_not_raise(self):
        partial = self.adapter.adapt(diagnostic_array(status("empty_component")))
        empty = self.adapter.adapt(diagnostic_array())
        self.assertEqual(partial["telemetry"], {})
        self.assertEqual(empty["telemetry"], {})
        self.assertTrue(partial["limitations"])
        self.assertTrue(empty["limitations"])

    def test_custom_vendor_key_mapping_is_supported(self):
        vendor = ROS2TelemetryAdapter(
            "V-1", key_mappings={"drive_temp": "motor_temperature"}
        )
        record = vendor.adapt(diagnostic_array(status(
            "drive", kv("drive_temp", "41 C")
        )))
        self.assertEqual(record["telemetry"]["motor_temperature"], 41.0)
        self.assertEqual(record["source_metadata"]["source_keys"]["motor_temperature"], ["drive_temp"])

    def test_adapter_emits_no_reliability_inference_or_actions(self):
        record = self.adapter.adapt(diagnostic_array(status(
            "motor", kv("motor_temperature", "40 C")
        )))
        for forbidden in ("risk", "diagnosis", "severity", "reliability_state", "recommendation", "probability"):
            self.assertNotIn(forbidden, record)
        self.assertIn("motor_temperature", record["telemetry"])

    def test_genesis_core_and_facade_accept_adapter_output_without_ros_imports(self):
        ros_available = importlib.util.find_spec("rclpy") is not None
        # Availability is recorded truthfully; importing Genesis must not pull
        # ROS into its module graph regardless of whether a runtime is present.
        self.assertIsInstance(ros_available, bool)
        self.assertNotIn("rclpy", sys.modules)
        record = self.adapter.adapt(diagnostic_array(
            status("thermal", kv("motor_temperature", "40 C")),
            stamp={"sec": 1, "nanosec": 0},
        ))
        result = Genesis().investigate(record)
        self.assertEqual(result["robot"]["robot_id"], "R-ROS-1")
        self.assertEqual(result["processing"]["observation_count"], 1)
        json.dumps(record)


if __name__ == "__main__":
    unittest.main()
