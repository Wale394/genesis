"""Optional read-only MQTT telemetry connector for KORDEX/Genesis.

Expected UTF-8 JSON payload (one observation per MQTT message)::

    {
      "robot_id": "robot-01",
      "timestamp": 1730000000.25,
      "sequence_number": 42,
      "manufacturer": "Example Robotics",
      "robot_type": "AMR",
      "signals": {"motor_temperature": 42.5, "battery_level": 81},
      "units": {"motor_temperature": "C", "battery_level": "%"},
      "quality": "AVAILABLE",
      "provenance": {"controller": "drive-unit"}
    }

This connector subscribes only. It never publishes messages or issues robot
commands. Broker authentication does not by itself prove the physical origin
or correctness of telemetry; provenance says that explicitly.
"""

from __future__ import annotations

import json
import math
from numbers import Real
import time
from queue import Empty, Queue
from threading import Event, Lock
from typing import Callable

from genesis_system.adapters.telemetry_connector import (
    ConnectorStatus,
    GENESIS_TELEMETRY_FIELDS,
    SignalDescriptor,
    TelemetryConnector,
    TelemetryPacket,
)


class MQTTTelemetryConnector(TelemetryConnector):
    """Subscribe to a configured MQTT topic and expose messages as packets.

    ``client_factory`` is an optional test seam. Production use lazily imports
    ``paho-mqtt`` so offline and non-MQTT users do not need that dependency.
    """

    def __init__(
        self,
        *,
        host: str,
        topic: str,
        port: int = 1883,
        client_id: str = "kordex-telemetry-reader",
        username: str | None = None,
        password: str | None = None,
        tls: bool = False,
        qos: int = 0,
        keepalive: int = 30,
        connect_timeout: float = 5.0,
        stale_after: float | None = None,
        robot_id: str | None = None,
        manufacturer: str | None = None,
        robot_type: str | None = None,
        client_factory: Callable | None = None,
        connector_id: str = "mqtt",
    ):
        if not isinstance(host, str) or not host.strip():
            raise ValueError("host is required")
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("topic is required")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("port must be an integer from 1 to 65535")
        if qos not in (0, 1, 2):
            raise ValueError("qos must be 0, 1, or 2")
        if connect_timeout <= 0 or keepalive <= 0:
            raise ValueError("connect_timeout and keepalive must be positive")
        if stale_after is not None and (
            isinstance(stale_after, bool) or not isinstance(stale_after, (int, float))
            or not math.isfinite(float(stale_after)) or stale_after <= 0
        ):
            raise ValueError("stale_after must be a positive finite number or None")
        if (username is None) != (password is None):
            raise ValueError("username and password must be supplied together")
        self.host = host.strip()
        self.topic = topic.strip()
        self.port = port
        self.client_id = client_id
        self.username = username
        self.password = password
        self.tls = bool(tls)
        self.qos = qos
        self.keepalive = keepalive
        self.connect_timeout = float(connect_timeout)
        self.stale_after = float(stale_after) if stale_after is not None else None
        self.robot_id = robot_id
        self.manufacturer = manufacturer
        self.robot_type = robot_type
        self.connector_id = connector_id
        self._client_factory = client_factory
        self._client = None
        self._status = ConnectorStatus.DISCONNECTED
        self._connected_event = Event()
        self._messages: Queue[TelemetryPacket] = Queue()
        self._lock = Lock()
        self._signals: dict[str, SignalDescriptor] = {}
        self._last_error: str | None = None
        self._connected_monotonic: float | None = None
        self._last_message_monotonic: float | None = None

    @property
    def last_error(self) -> str | None:
        """Last connection or payload error, without credentials or payload dumps."""
        return self._last_error

    def _make_client(self):
        if self._client_factory is not None:
            return self._client_factory()
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise RuntimeError(
                "MQTT support requires the optional 'paho-mqtt' package; install it with: "
                "python -m pip install paho-mqtt"
            ) from exc
        try:
            return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
        except (AttributeError, TypeError):  # paho-mqtt 1.x compatibility
            return mqtt.Client(client_id=self.client_id)

    def connect(self) -> None:
        if self._status in {ConnectorStatus.CONNECTING, ConnectorStatus.CONNECTED}:
            return
        self._status = ConnectorStatus.CONNECTING
        self._last_error = None
        self._connected_event.clear()
        client = None
        try:
            client = self._make_client()
            self._client = client
            if self.username is not None:
                client.username_pw_set(self.username, self.password)
            if self.tls:
                client.tls_set()
            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect
            client.on_message = self._on_message
            client.connect(self.host, self.port, self.keepalive)
            client.loop_start()
            if not self._connected_event.wait(self.connect_timeout):
                self._status = ConnectorStatus.ERROR
                self._last_error = "Timed out waiting for MQTT broker connection."
                try:
                    client.loop_stop()
                finally:
                    raise TimeoutError(self._last_error)
            if self._status != ConnectorStatus.CONNECTED:
                raise ConnectionError(self._last_error or "MQTT broker rejected the connection.")
        except Exception as exc:
            if self._status != ConnectorStatus.ERROR:
                self._status = ConnectorStatus.ERROR
                self._last_error = f"MQTT connection failed ({type(exc).__name__})."
            if client is not None:
                try:
                    client.loop_stop()
                except Exception:
                    pass
            raise

    def disconnect(self) -> None:
        client, self._client = self._client, None
        self._connected_event.clear()
        if client is not None:
            try:
                client.disconnect()
            finally:
                try:
                    client.loop_stop()
                finally:
                    self._status = ConnectorStatus.DISCONNECTED
        else:
            self._status = ConnectorStatus.DISCONNECTED

    def get_status(self) -> ConnectorStatus:
        # Freshness is based on local monotonic arrival time, not source wall-clock
        # timestamps, which may be skewed or represent recorded/replayed data.
        if self._status == ConnectorStatus.CONNECTED and self.stale_after is not None:
            baseline = self._last_message_monotonic or self._connected_monotonic
            if baseline is not None and time.monotonic() - baseline > self.stale_after:
                return ConnectorStatus.DEGRADED
        return self._status

    def discover_signals(self) -> tuple[SignalDescriptor, ...]:
        with self._lock:
            return tuple(self._signals[name] for name in sorted(self._signals))

    def read(self, timeout: float | None = None) -> TelemetryPacket | None:
        if self.get_status() not in {ConnectorStatus.CONNECTED, ConnectorStatus.DEGRADED}:
            raise RuntimeError("MQTT connector is not connected")
        if timeout is not None and timeout < 0:
            raise ValueError("timeout cannot be negative")
        try:
            return self._messages.get(timeout=timeout)
        except Empty:
            return None

    def _on_connect(self, client, userdata, flags, reason_code, *extra):
        del userdata, flags, extra
        try:
            failed = bool(getattr(reason_code, "is_failure", False))
            if not failed:
                failed = int(reason_code) != 0
        except (TypeError, ValueError):
            failed = str(reason_code).strip().lower() not in {"success", "success (0)", "0"}
        if failed:
            self._status = ConnectorStatus.ERROR
            self._last_error = "MQTT broker rejected the connection."
            self._connected_event.set()
            return
        try:
            client.subscribe(self.topic, qos=self.qos)
            self._connected_monotonic = time.monotonic()
            self._last_message_monotonic = None
            self._status = ConnectorStatus.CONNECTED
        except Exception as exc:
            self._status = ConnectorStatus.ERROR
            self._last_error = f"MQTT subscription failed ({type(exc).__name__})."
        finally:
            self._connected_event.set()

    def _on_disconnect(self, client, userdata, *args):
        del client, userdata
        if self._status not in {ConnectorStatus.DISCONNECTED, ConnectorStatus.ERROR}:
            self._status = ConnectorStatus.DEGRADED
            self._last_error = "MQTT connection was lost."

    def _on_message(self, client, userdata, message):
        del client, userdata
        try:
            raw = json.loads(message.payload.decode("utf-8"), parse_constant=self._reject_json_constant)
            packet = self._decode_payload(raw, topic=getattr(message, "topic", self.topic))
            with self._lock:
                for name, value in packet.signals.items():
                    if isinstance(value, bool):
                        data_type = "boolean"
                    elif isinstance(value, Real):
                        data_type = "number"
                    elif isinstance(value, str):
                        data_type = "string"
                    else:
                        data_type = "object"
                    self._signals[name] = SignalDescriptor(name, data_type, packet.units.get(name))
            self._last_message_monotonic = time.monotonic()
            self._status = ConnectorStatus.CONNECTED
            self._messages.put(packet)
        except Exception as exc:
            # Keep the consumer alive, but make malformed input visible.
            self._last_error = f"Rejected MQTT telemetry message ({type(exc).__name__})."
            if self._status == ConnectorStatus.CONNECTED:
                self._status = ConnectorStatus.DEGRADED

    @staticmethod
    def _reject_json_constant(value):
        raise ValueError(f"non-standard JSON constant {value} is not allowed")

    def _decode_payload(self, payload, *, topic):
        if not isinstance(payload, dict):
            raise ValueError("MQTT payload must be a JSON object")
        robot_id = payload.get("robot_id") or self.robot_id
        if not isinstance(robot_id, str) or not robot_id.strip():
            raise ValueError("robot_id is required in payload or connector configuration")
        signals = payload.get("signals")
        if not isinstance(signals, dict) or not signals:
            raise ValueError("signals must be a non-empty JSON object")
        for name, value in signals.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("signal names must be non-empty strings")
            if isinstance(value, (dict, list)) or value is None:
                raise ValueError(f"signal {name!r} must be a non-null scalar")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"signal {name!r} must be finite")
            if name in GENESIS_TELEMETRY_FIELDS and name != "robot_state":
                if isinstance(value, bool) or not isinstance(value, Real):
                    raise ValueError(f"canonical numeric signal {name!r} must be numeric")
        units = payload.get("units", {})
        provenance = payload.get("provenance", {})
        if not isinstance(units, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in units.items()):
            raise ValueError("units must map signal names to unit strings")
        if not isinstance(provenance, dict):
            raise ValueError("provenance must be a JSON object")
        sequence = payload.get("sequence_number")
        if isinstance(sequence, bool) or (sequence is not None and not isinstance(sequence, Real)):
            raise ValueError("sequence_number must be numeric")
        if isinstance(sequence, Real) and not math.isfinite(float(sequence)):
            raise ValueError("sequence_number must be finite")
        quality = payload.get("quality", "AVAILABLE")
        if not isinstance(quality, str) or not quality.strip():
            raise ValueError("quality must be a non-empty string")
        limitations = payload.get("limitations", [])
        if not isinstance(limitations, list) or not all(isinstance(item, str) for item in limitations):
            raise ValueError("limitations must be a list of strings")
        return TelemetryPacket(
            robot_id=robot_id.strip(),
            source="mqtt",
            timestamp=payload.get("timestamp"),
            signals=signals,
            manufacturer=payload.get("manufacturer", self.manufacturer),
            robot_type=payload.get("robot_type", self.robot_type),
            sequence_number=sequence,
            units=units,
            provenance={
                **provenance,
                "transport": "MQTT",
                "topic": topic,
                "input_kind": "MQTT JSON message; physical source not independently authenticated by KORDEX",
            },
            limitations=tuple(limitations),
            quality=quality,
        )
