import json
import time
import unittest
from types import SimpleNamespace

from genesis_system.adapters.telemetry_connector import ConnectorStatus
from mqtt_telemetry_connector import MQTTTelemetryConnector


class FakeMQTTClient:
    def __init__(self):
        self.subscriptions = []
        self.connected_args = None
        self.username_password = None
        self.tls_enabled = False
        self.stopped = False

    def username_pw_set(self, username, password):
        self.username_password = (username, password)

    def tls_set(self):
        self.tls_enabled = True

    def connect(self, host, port, keepalive):
        self.connected_args = (host, port, keepalive)

    def loop_start(self):
        self.on_connect(self, None, {}, 0)

    def loop_stop(self):
        self.stopped = True

    def subscribe(self, topic, qos=0):
        self.subscriptions.append((topic, qos))

    def disconnect(self):
        pass

    def send(self, payload, topic="robots/robot-01/telemetry"):
        self.on_message(self, None, SimpleNamespace(payload=payload, topic=topic, qos=0, retain=False))


class MQTTTelemetryConnectorTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeMQTTClient()
        self.connector = MQTTTelemetryConnector(
            host="localhost", topic="robots/+/telemetry", robot_id="robot-01",
            client_factory=lambda: self.client,
        )

    def test_subscribes_read_only_and_exposes_status(self):
        self.connector.connect()
        self.assertEqual(self.connector.get_status(), ConnectorStatus.CONNECTED)
        self.assertEqual(self.client.subscriptions, [("robots/+/telemetry", 0)])
        self.assertFalse(hasattr(self.client, "publish"))
        self.connector.disconnect()
        self.assertEqual(self.connector.get_status(), ConnectorStatus.DISCONNECTED)

    def test_json_message_becomes_packet_with_provenance_and_units(self):
        self.connector.connect()
        payload = {
            "robot_id": "robot-01", "timestamp": 123.5, "sequence_number": 7,
            "signals": {"motor_temperature": 42.5, "battery_level": 80},
            "units": {"motor_temperature": "C", "battery_level": "%"},
        }
        self.client.send(json.dumps(payload).encode())
        packet = self.connector.read(timeout=0.1)
        self.assertEqual(packet.robot_id, "robot-01")
        self.assertEqual(packet.source, "mqtt")
        self.assertEqual(packet.signals["motor_temperature"], 42.5)
        self.assertEqual(packet.units["motor_temperature"], "C")
        self.assertEqual(packet.sequence_number, 7)
        self.assertEqual(packet.provenance["topic"], "robots/robot-01/telemetry")
        self.assertIn("not independently authenticated", packet.provenance["input_kind"])
        self.assertEqual({item.name for item in self.connector.discover_signals()}, {"motor_temperature", "battery_level"})

    def test_bad_message_is_rejected_and_connector_reports_degraded(self):
        self.connector.connect()
        self.client.send(b'{"robot_id":"robot-01","signals":{"motor_temperature":NaN}}')
        self.assertEqual(self.connector.get_status(), ConnectorStatus.DEGRADED)
        self.assertIn("Rejected MQTT telemetry message", self.connector.last_error)
        self.assertIsNone(self.connector.read(timeout=0))

    def test_missing_robot_identity_is_rejected(self):
        connector = MQTTTelemetryConnector(host="localhost", topic="robot/telemetry", client_factory=lambda: self.client)
        connector.connect()
        self.client.send(json.dumps({"signals": {"motor_temperature": 42}}).encode())
        self.assertEqual(connector.get_status(), ConnectorStatus.DEGRADED)
        self.assertIn("Rejected MQTT telemetry message", connector.last_error)

    def test_invalid_configuration_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "topic is required"):
            MQTTTelemetryConnector(host="localhost", topic=" ")
        with self.assertRaisesRegex(ValueError, "username and password"):
            MQTTTelemetryConnector(host="localhost", topic="robot/telemetry", username="user")


    def test_stale_telemetry_marks_status_degraded_and_fresh_message_recovers(self):
        client = FakeMQTTClient()
        connector = MQTTTelemetryConnector(
            host="localhost", topic="robots/+/telemetry", robot_id="robot-01",
            stale_after=0.02, client_factory=lambda: client,
        )
        connector.connect()
        self.assertEqual(connector.get_status(), ConnectorStatus.CONNECTED)
        time.sleep(0.03)
        self.assertEqual(connector.get_status(), ConnectorStatus.DEGRADED)
        client.send(json.dumps({
            "robot_id": "robot-01", "timestamp": 123.5,
            "signals": {"motor_temperature": 42.5},
            "units": {"motor_temperature": "C"},
        }).encode())
        self.assertEqual(connector.get_status(), ConnectorStatus.CONNECTED)
        connector.disconnect()

    def test_reconnect_callback_restores_connected_state_and_resubscribes(self):
        self.connector.connect()
        self.connector._on_disconnect(self.client, None)
        self.assertEqual(self.connector.get_status(), ConnectorStatus.DEGRADED)
        self.connector._on_connect(self.client, None, {}, 0)
        self.assertEqual(self.connector.get_status(), ConnectorStatus.CONNECTED)
        self.assertEqual(len(self.client.subscriptions), 2)
        self.connector.disconnect()

    def test_invalid_stale_after_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "stale_after"):
            MQTTTelemetryConnector(host="localhost", topic="robot/telemetry", stale_after=0)


if __name__ == "__main__":
    unittest.main()
