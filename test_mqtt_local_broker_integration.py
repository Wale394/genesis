"""Local MQTT protocol smoke test without third-party broker/client packages.

The tiny broker/client below implement only MQTT 3.1.1 QoS-0 CONNECT,
SUBSCRIBE, PUBLISH, and DISCONNECT packets. They are test fixtures, not
production MQTT implementations. This validates KORDEX's connector lifecycle,
subscription, message decoding, provenance, and engine handoff over a real local
TCP socket; it does not validate interoperability with paho-mqtt or a vendor broker.
"""
from __future__ import annotations

import json
import socket
import threading
import unittest
from types import SimpleNamespace

from genesis import Genesis
from genesis_system.adapters.telemetry_connector import investigate_packet
from mqtt_telemetry_connector import MQTTTelemetryConnector


def _encode_remaining_length(length: int) -> bytes:
    encoded = bytearray()
    while True:
        digit = length % 128
        length //= 128
        if length:
            digit |= 0x80
        encoded.append(digit)
        if not length:
            return bytes(encoded)


def _packet(first_byte: int, body: bytes) -> bytes:
    return bytes([first_byte]) + _encode_remaining_length(len(body)) + body


def _read_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            raise ConnectionError("socket closed during MQTT packet")
        data.extend(part)
    return bytes(data)


def _read_packet(sock: socket.socket) -> tuple[int, bytes]:
    first = _read_exact(sock, 1)[0]
    multiplier = 1
    remaining = 0
    for _ in range(4):
        digit = _read_exact(sock, 1)[0]
        remaining += (digit & 0x7F) * multiplier
        if not digit & 0x80:
            break
        multiplier *= 128
    else:
        raise ValueError("malformed MQTT remaining length")
    return first, _read_exact(sock, remaining)


class _LocalBroker:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.host, self.port = self.server.getsockname()
        self.subscribed = threading.Event()
        self.ready = threading.Event()
        self._client = None
        self._error = None
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        try:
            self.server.settimeout(3.0)
            client, _ = self.server.accept()
            self._client = client
            client.settimeout(3.0)
            packet_type, _body = _read_packet(client)
            if packet_type >> 4 != 1:
                raise AssertionError("expected MQTT CONNECT")
            client.sendall(_packet(0x20, b"\x00\x00"))  # CONNACK success
            self.ready.set()
            while not self._closed.is_set():
                try:
                    packet_type, body = _read_packet(client)
                except (ConnectionError, OSError):
                    return
                kind = packet_type >> 4
                if kind == 8:  # SUBSCRIBE
                    if len(body) < 5:
                        raise AssertionError("malformed MQTT SUBSCRIBE")
                    packet_id = body[:2]
                    topic_len = int.from_bytes(body[2:4], "big")
                    if len(body) < 4 + topic_len + 1:
                        raise AssertionError("malformed MQTT subscription topic")
                    topic = body[4:4 + topic_len].decode("utf-8")
                    if topic != "robots/+/telemetry":
                        raise AssertionError(f"unexpected subscription topic: {topic}")
                    client.sendall(_packet(0x90, packet_id + b"\x00"))  # SUBACK QoS 0
                    self.subscribed.set()
                elif kind == 14:  # DISCONNECT
                    return
                else:
                    raise AssertionError(f"unexpected MQTT packet type {kind}")
        except Exception as exc:
            self._error = exc
            self.ready.set()
            self.subscribed.set()

    def publish(self, topic: str, payload: bytes):
        if not self.subscribed.wait(2.0):
            raise TimeoutError("client did not subscribe to the telemetry topic")
        if self._error:
            raise RuntimeError("local broker failed") from self._error
        topic_bytes = topic.encode("utf-8")
        body = len(topic_bytes).to_bytes(2, "big") + topic_bytes + payload
        self._client.sendall(_packet(0x30, body))  # PUBLISH QoS 0

    def close(self):
        self._closed.set()
        try:
            if self._client:
                self._client.close()
        except OSError:
            pass
        self.server.close()
        self._thread.join(timeout=1.0)


class _WireMQTTClient:
    """Minimal MQTT 3.1.1 client used only to drive the connector test seam."""
    def __init__(self):
        self.sock = None
        self._thread = None
        self._stopped = threading.Event()
        self._packet_id = 1

    def connect(self, host, port, keepalive):
        self.sock = socket.create_connection((host, port), timeout=2.0)
        client_id = b"kordex-local-test"
        variable = b"\x00\x04MQTT\x04\x02" + int(keepalive).to_bytes(2, "big")
        payload = len(client_id).to_bytes(2, "big") + client_id
        self.sock.sendall(_packet(0x10, variable + payload))

    def loop_start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        try:
            while not self._stopped.is_set():
                packet_type, body = _read_packet(self.sock)
                kind = packet_type >> 4
                if kind == 2:  # CONNACK
                    reason_code = body[1]
                    self.on_connect(self, None, {}, reason_code)
                elif kind == 3:  # PUBLISH
                    topic_len = int.from_bytes(body[:2], "big")
                    topic = body[2:2 + topic_len].decode("utf-8")
                    payload = body[2 + topic_len:]
                    self.on_message(self, None, SimpleNamespace(topic=topic, payload=payload))
                elif kind == 9:  # SUBACK
                    continue
                else:
                    raise AssertionError(f"unexpected broker packet type {kind}")
        except (OSError, ConnectionError):
            return

    def subscribe(self, topic, qos=0):
        topic_bytes = topic.encode("utf-8")
        body = self._packet_id.to_bytes(2, "big") + len(topic_bytes).to_bytes(2, "big") + topic_bytes + bytes([qos])
        self.sock.sendall(_packet(0x82, body))
        self._packet_id += 1

    def loop_stop(self):
        self._stopped.set()
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=1.0)

    def disconnect(self):
        if self.sock:
            try:
                self.sock.sendall(b"\xE0\x00")
            except OSError:
                pass


class MQTTLocalBrokerIntegrationTests(unittest.TestCase):
    def test_local_broker_message_reaches_genesis_pipeline_read_only(self):
        broker = _LocalBroker()
        client = _WireMQTTClient()
        connector = MQTTTelemetryConnector(
            host=broker.host,
            port=broker.port,
            topic="robots/+/telemetry",
            connect_timeout=2,
            client_factory=lambda: client,
        )
        try:
            connector.connect()
            self.assertTrue(broker.subscribed.wait(2), "connector never subscribed")
            payload = {
                "robot_id": "robot-local-01",
                "timestamp": 1720000000.25,
                "sequence_number": 17,
                "signals": {"motor_temperature": 43.5, "battery_level": 76},
                "units": {"motor_temperature": "C", "battery_level": "%"},
                "provenance": {"source_system": "local-broker-test"},
            }
            broker.publish("robots/robot-local-01/telemetry", json.dumps(payload).encode("utf-8"))
            packet = connector.read(timeout=2)
            self.assertIsNotNone(packet)
            record, result = investigate_packet(packet, Genesis(), connector_id=connector.connector_id)
            self.assertEqual(record["identity"]["robot_id"], "robot-local-01")
            self.assertEqual(record["telemetry"]["motor_temperature"], 43.5)
            self.assertEqual(record["telemetry"]["time_step"], 1720000000.25)
            self.assertEqual(record["source_metadata"]["units"]["motor_temperature"], "C")
            self.assertEqual(record["source_metadata"]["provenance"]["source_system"], "local-broker-test")
            self.assertEqual(result["robot"]["robot_id"], "robot-local-01")
            self.assertEqual(result["processing"]["observation_count"], 1)
            self.assertIn("not independently authenticated", packet.provenance["input_kind"])
        finally:
            connector.disconnect()
            broker.close()


if __name__ == "__main__":
    unittest.main()
