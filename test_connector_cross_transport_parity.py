"""Ensure different adapters preserve common signal meaning into Genesis."""
import unittest

from genesis import Genesis
from ros2_telemetry_adapter import ROS2TelemetryAdapter
from telemetry_connector import investigate_packet


def kv(key, value):
    return {"key": key, "value": value}


def status(name, *values):
    return {"name": name, "values": list(values)}


class ConnectorCrossTransportParityTests(unittest.TestCase):
    def test_ros2_and_mqtt_shapes_map_same_temperature_to_same_engine_field(self):
        ros2 = ROS2TelemetryAdapter("robot-parity-01", manufacturer="Example", robot_type="AMR")
        ros_packet = ros2.adapt_packet({
            "header": {"stamp": {"sec": 100, "nanosec": 0}},
            "status": [status("drive", kv("motor_temperature", "43.5 C"))],
        })
        from telemetry_connector import TelemetryPacket
        mqtt_packet = TelemetryPacket(
            robot_id="robot-parity-01",
            source="mqtt",
            timestamp=100.0,
            signals={"motor_temperature": 43.5},
            manufacturer="Example",
            robot_type="AMR",
            units={"motor_temperature": "C"},
            provenance={"transport": "MQTT", "input_kind": "test payload; source not independently authenticated"},
        )
        ros_record, ros_result = investigate_packet(ros_packet, Genesis(), connector_id="ros2-payload-adapter")
        mqtt_record, mqtt_result = investigate_packet(mqtt_packet, Genesis(), connector_id="mqtt")
        self.assertEqual(ros_record["telemetry"]["motor_temperature"], mqtt_record["telemetry"]["motor_temperature"])
        self.assertEqual(ros_record["identity"]["robot_id"], mqtt_record["identity"]["robot_id"])
        self.assertEqual(ros_record["source_metadata"]["units"]["motor_temperature"], mqtt_record["source_metadata"]["units"]["motor_temperature"])
        self.assertEqual(ros_result["robot"]["robot_id"], mqtt_result["robot"]["robot_id"])
        self.assertEqual(ros_result["processing"]["observation_count"], mqtt_result["processing"]["observation_count"])
        self.assertEqual(ros_record["source_metadata"]["connector_id"], "ros2-payload-adapter")
        self.assertEqual(mqtt_record["source_metadata"]["connector_id"], "mqtt")


if __name__ == "__main__":
    unittest.main()
