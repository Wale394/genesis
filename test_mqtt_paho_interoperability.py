"""Optional interoperability check against the real paho-mqtt client.

Requires paho-mqtt to be installed. The broker is a minimal test fixture, not a
production broker; this specifically checks client-library wire interoperability.
"""
import importlib.util
import json
import unittest

from mqtt_telemetry_connector import MQTTTelemetryConnector
from test_mqtt_local_broker_integration import _LocalBroker

try:
    import paho.mqtt.client  # noqa: F401
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False


@unittest.skipUnless(PAHO_AVAILABLE, "optional dependency paho-mqtt is not installed")
class PahoMQTTInteroperabilityTests(unittest.TestCase):
    def test_real_paho_client_subscribes_and_delivers_telemetry(self):
        broker = _LocalBroker()
        connector = MQTTTelemetryConnector(
            host=broker.host,
            port=broker.port,
            topic="robots/+/telemetry",
            connect_timeout=2,
            client_id="kordex-paho-interoperability-test",
        )
        try:
            connector.connect()
            self.assertTrue(broker.subscribed.wait(2), "Paho client did not subscribe")
            payload = {
                "robot_id": "robot-paho-01",
                "timestamp": 1720000001.5,
                "sequence_number": 18,
                "signals": {"motor_temperature": 44.0},
                "units": {"motor_temperature": "C"},
                "provenance": {"test": "paho-client-interoperability"},
            }
            broker.publish("robots/robot-paho-01/telemetry", json.dumps(payload).encode("utf-8"))
            packet = connector.read(timeout=2)
            self.assertIsNotNone(packet)
            self.assertEqual(packet.robot_id, "robot-paho-01")
            self.assertEqual(packet.signals["motor_temperature"], 44.0)
            self.assertEqual(packet.units["motor_temperature"], "C")
        finally:
            connector.disconnect()
            broker.close()


if __name__ == "__main__":
    unittest.main()
