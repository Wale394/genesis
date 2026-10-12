# Genesis telemetry connector contract — initial implementation

## Purpose

Provide one transport-independent boundary between telemetry acquisition and
Genesis' existing reliability investigation pipeline. A connector can later be
implemented for ROS 2, a vendor SDK/API, MQTT, WebSocket, a custom documented
protocol, or recorded files. Adding a connector must not require rewriting the
reliability engine.

## Contract

- `TelemetryConnector` defines `connect`, `disconnect`, `get_status`,
  `discover_signals`, and `read`.
- `TelemetryPacket` represents one observation and carries robot identity,
  source, source timestamp, source-named signals, declared units, sequence
  number, provenance, data-quality label, and limitations.
- Each transport adapter is responsible for interpreting its protocol and
  converting values into explicitly declared units. The common contract does
  not guess units or silently convert them.
- `to_genesis_record` maps only fields currently understood by Genesis. Unknown
  signals remain visible in metadata and limitations rather than being passed
  to the engine as if they were understood.
- `investigate_packet` converts one packet and sends it through the existing `Genesis.investigate` API, returning both the exact input record and the engine result.
- A timestamp is used as Genesis `time_step` only when it is already numeric.
  Non-numeric timestamps are preserved as metadata; Genesis may use its
  ingestion-order fallback. No timestamp parsing or ordering is guessed here.
- The interface exposes no robot command or control methods. A connector's
  `CONNECTED` state means a transport is connected, not that source identity is
  authenticated or that the robot is safe.

## Current limits

This is the contract and deterministic recorded-data reference connector, not a
live ROS 2, vendor API, or MQTT implementation. Genesis currently analyzes a
bounded set of canonical telemetry fields. Platform-specific signals such as
joint torque need an explicit validated mapping and/or future engine support.

## Small targeted check

From the repository root:

```powershell
python -m unittest test_telemetry_connector_contract.py
```

This checks contract validation, signal mapping, provenance/units preservation,
end-of-stream behavior, and compatibility with the existing `Genesis` facade.

## Optional MQTT connector

`genesis_system.adapters.mqtt_telemetry_connector.MQTTTelemetryConnector` is a
read-only MQTT subscriber. It uses the same `TelemetryPacket` contract as the
ROS 2 payload adapter and does not publish commands. To use a real broker,
install the optional dependency with `python -m pip install paho-mqtt`, then
configure the broker host and an explicit telemetry topic. Enable TLS and
broker authentication where supported by the deployment.

Each MQTT message must be UTF-8 JSON with a `signals` object and a robot ID
(either in the payload or supplied as configured metadata). Optional fields
include `timestamp`, `sequence_number`, `manufacturer`, `robot_type`, `units`,
`quality`, `provenance`, and `limitations`. See `mqtt_telemetry_connector.py`
for the exact example schema. Signal names and units are not guessed or
converted by this transport connector. Only canonical fields currently
supported by Genesis are forwarded by `TelemetryPacket.to_genesis_record()`;
other signals remain visible as limitations.

The connector's source metadata states that the physical origin of a message
is not independently authenticated by KORDEX. A broker connection is not
proof that a sensor is correct or that a message truly came from the named
robot. Start with recorded or simulated messages before a supervised read-only
trial. This connector has no publish or robot-control method.
