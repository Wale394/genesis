import unittest

from genesis import Genesis
from telemetry_connector import (
    ConnectorStatus,
    RecordedTelemetryConnector,
    SignalDescriptor,
    TelemetryPacket,
    investigate_packet,
)


class TelemetryConnectorContractTests(unittest.TestCase):
    def packet(self, **overrides):
        values = {
            "robot_id": "robot-test-01",
            "source": "vendor-api",
            "timestamp": 100.0,
            "signals": {"drive_temp": 40.0, "battery_v": 48.0, "joint_torque": 3.2},
            "manufacturer": "Example Robotics",
            "robot_type": "AMR",
            "sequence_number": 1,
            "units": {"drive_temp": "C", "battery_v": "V", "joint_torque": "Nm"},
            "provenance": {"transport": "https", "synthetic": True},
        }
        values.update(overrides)
        return TelemetryPacket(**values)

    def test_packet_maps_supported_signals_and_reports_unknown_ones(self):
        record = self.packet().to_genesis_record(field_mappings={
            "drive_temp": "motor_temperature", "battery_v": "battery_voltage",
        }, connector_id="vendor-x")
        self.assertEqual(record["identity"]["robot_id"], "robot-test-01")
        self.assertEqual(record["telemetry"]["motor_temperature"], 40.0)
        self.assertEqual(record["telemetry"]["battery_voltage"], 48.0)
        self.assertEqual(record["telemetry"]["time_step"], 100.0)
        self.assertEqual(record["source_metadata"]["connector_id"], "vendor-x")
        self.assertEqual(record["source_metadata"]["units"], {
            "motor_temperature": "C", "battery_voltage": "V",
        })
        self.assertEqual(record["source_metadata"]["unmapped_signals"], ["joint_torque"])
        self.assertTrue(any("joint_torque" in item for item in record["limitations"]))

    def test_non_numeric_timestamp_is_preserved_without_inventing_time_step(self):
        record = self.packet(timestamp="2026-10-11T12:00:00Z").to_genesis_record(
            field_mappings={"drive_temp": "motor_temperature"}
        )
        self.assertNotIn("time_step", record["telemetry"])
        self.assertEqual(record["source_metadata"]["timestamp"], "2026-10-11T12:00:00Z")
        self.assertTrue(any("not numeric" in item for item in record["limitations"]))

    def test_connector_lifecycle_signal_discovery_and_end_of_stream(self):
        connector = RecordedTelemetryConnector(
            [self.packet()],
            signal_descriptors=[SignalDescriptor("drive_temp", unit="C")],
        )
        self.assertEqual(connector.get_status(), ConnectorStatus.DISCONNECTED)
        with self.assertRaisesRegex(RuntimeError, "not connected"):
            connector.read()
        connector.connect()
        self.assertEqual(connector.get_status(), ConnectorStatus.CONNECTED)
        self.assertEqual(connector.discover_signals()[0].name, "drive_temp")
        self.assertEqual(connector.read().robot_id, "robot-test-01")
        self.assertIsNone(connector.read())
        connector.disconnect()
        self.assertEqual(connector.get_status(), ConnectorStatus.DISCONNECTED)

    def test_bad_packet_identity_and_unsupported_mapping_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "robot_id is required"):
            self.packet(robot_id="")
        with self.assertRaisesRegex(ValueError, "unsupported Genesis target"):
            self.packet().to_genesis_record(field_mappings={"drive_temp": "joint_torque"})

    def test_normalized_packet_can_enter_existing_genesis_pipeline(self):
        packet = self.packet(signals={"drive_temp": 40.0}, units={"drive_temp": "C"})
        record, result = investigate_packet(
            packet,
            Genesis(),
            field_mappings={"drive_temp": "motor_temperature"},
            connector_id="vendor-x",
        )
        self.assertEqual(record["source_metadata"]["connector_id"], "vendor-x")
        self.assertEqual(result["robot"]["robot_id"], "robot-test-01")
        self.assertEqual(result["processing"]["observation_count"], 1)


if __name__ == "__main__":
    unittest.main()
