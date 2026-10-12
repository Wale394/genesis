import json
import unittest
from types import SimpleNamespace

from genesis import Genesis
from genesis_system.adapters.telemetry_connector import investigate_packet
from mqtt_telemetry_connector import MQTTTelemetryConnector


class FakeMQTTClient:
    def connect(self, *args):
        pass

    def loop_start(self):
        self.on_connect(self, None, {}, 0)

    def loop_stop(self):
        pass

    def subscribe(self, topic, qos=0):
        self.subscription = (topic, qos)

    def disconnect(self):
        pass

    def send(self, payload):
        self.on_message(self, None, SimpleNamespace(payload=payload, topic="robot/robot-01/telemetry"))


class MQTTConnectorEngineIntegrationTests(unittest.TestCase):
    def test_mqtt_packet_uses_same_genesis_investigation_pipeline(self):
        client = FakeMQTTClient()
        connector = MQTTTelemetryConnector(
            host="localhost", topic="robot/+/telemetry", client_factory=lambda: client,
        )
        connector.connect()
        client.send(json.dumps({
            "robot_id": "robot-01",
            "timestamp": 100.0,
            "sequence_number": 1,
            "signals": {"motor_temperature": 41.0},
            "units": {"motor_temperature": "C"},
        }).encode())
        packet = connector.read(timeout=0.1)
        record, result = investigate_packet(packet, Genesis(), connector_id=connector.connector_id)
        self.assertEqual(record["identity"]["robot_id"], "robot-01")
        self.assertEqual(record["telemetry"]["motor_temperature"], 41.0)
        self.assertEqual(record["source_metadata"]["connector_id"], "mqtt")
        self.assertEqual(result["robot"]["robot_id"], "robot-01")
        self.assertEqual(result["processing"]["observation_count"], 1)
        connector.disconnect()


if __name__ == "__main__":
    unittest.main()
