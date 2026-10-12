import unittest

from genesis import Genesis
from ros2_telemetry_adapter import ROS2TelemetryAdapter
from telemetry_connector import investigate_packet


def kv(key, value):
    return {"key": key, "value": value}


def status(name, *values):
    return {"name": name, "values": list(values)}


def diagnostic_array(*statuses, stamp=None):
    return {"header": {"stamp": stamp} if stamp is not None else {}, "status": list(statuses)}


class ROS2ConnectorBridgeTests(unittest.TestCase):
    def setUp(self):
        self.adapter = ROS2TelemetryAdapter("robot-bridge-01", manufacturer="Example", robot_type="AMR")

    def test_ros2_payload_becomes_shared_packet_without_live_ros_dependency(self):
        message = diagnostic_array(
            status("drive", kv("motor_temperature", "40 C"), kv("battery_voltage", "48 V")),
            stamp={"sec": 100, "nanosec": 500_000_000},
        )
        packet = self.adapter.adapt_packet(message)
        self.assertEqual(packet.robot_id, "robot-bridge-01")
        self.assertEqual(packet.source, "ros2")
        self.assertEqual(packet.signals["motor_temperature"], 40.0)
        self.assertEqual(packet.signals["battery_voltage"], 48.0)
        self.assertEqual(packet.units["motor_temperature"], "C")
        self.assertEqual(packet.timestamp, {"sec": 100, "nanosec": 500_000_000})
        self.assertIn("acquisition not performed", packet.provenance["input_kind"])

    def test_packet_enters_existing_genesis_pipeline(self):
        message = diagnostic_array(status("drive", kv("motor_temperature", "40 C")))
        packet = self.adapter.adapt_packet(message)
        record, result = investigate_packet(packet, Genesis(), connector_id="ros2-payload-adapter")
        self.assertEqual(record["identity"]["robot_id"], "robot-bridge-01")
        self.assertEqual(record["telemetry"]["motor_temperature"], 40.0)
        self.assertEqual(record["source_metadata"]["connector_id"], "ros2-payload-adapter")
        self.assertEqual(result["robot"]["robot_id"], "robot-bridge-01")
        self.assertEqual(result["processing"]["observation_count"], 1)

    def test_unmapped_diagnostics_remain_visible_as_limitations(self):
        message = diagnostic_array(status("drive", kv("motor_temperature", "40 C"), kv("vendor_counter", "9")))
        packet = self.adapter.adapt_packet(message)
        self.assertTrue(any("vendor_counter" in item for item in packet.limitations))
        self.assertEqual(packet.provenance["ignored_keys"], ["vendor_counter"])

    def test_payload_without_supported_telemetry_is_rejected(self):
        message = diagnostic_array(status("drive", kv("vendor_counter", "9")))
        with self.assertRaisesRegex(ValueError, "no usable telemetry"):
            self.adapter.adapt_packet(message)


if __name__ == "__main__":
    unittest.main()
