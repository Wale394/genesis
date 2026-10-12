# KORDEX MQTT telemetry connector (experimental)

This optional connector lets a robot controller or gateway publish diagnostic
telemetry to an MQTT broker that KORDEX can subscribe to. It is **read-only**:
KORDEX subscribes to one configured topic and has no publish/command API in this
connector. MQTT support does not mean that every robot is automatically
compatible; a robot still needs an accessible, authorized telemetry interface
and a mapping from its signals to the fields KORDEX understands.

## 1. Install the optional dependency

From the GenesisLabcl project root:

```powershell
python -m pip install paho-mqtt
```

Users of offline analysis or other connectors do not need to install this
package. The connector imports it only when `connect()` is called.

## 2. Required message shape

Publish one UTF-8 JSON object per observation to the configured topic. Example:

```json
{
  "robot_id": "robot-01",
  "timestamp": 1730000000.25,
  "sequence_number": 42,
  "manufacturer": "Example Robotics",
  "robot_type": "AMR",
  "signals": {
    "motor_temperature": 42.5,
    "battery_level": 81
  },
  "units": {
    "motor_temperature": "C",
    "battery_level": "%"
  },
  "quality": "AVAILABLE",
  "provenance": {
    "controller": "drive-unit"
  }
}
```

`robot_id` can instead be provided as connector configuration. `signals` must
be a non-empty object of scalar values. Known numeric Genesis fields must be
numeric and finite; `robot_state` may be a string. Units are source-declared;
the connector does not guess or convert units. Use canonical field names when
possible, or explicitly configure `field_mappings` when converting the packet
for the Genesis engine. Unknown fields are not treated as analyzed signals.

## 3. Minimal consumer example

```python
from genesis import Genesis
from genesis_system.adapters.mqtt_telemetry_connector import MQTTTelemetryConnector
from genesis_system.adapters.telemetry_connector import investigate_packet

connector = MQTTTelemetryConnector(
    host="YOUR_BROKER_HOST",
    port=8883,
    topic="robots/robot-01/telemetry",
    robot_id="robot-01",
    username="YOUR_READ_ONLY_USERNAME",
    password="LOAD_FROM_YOUR_SECRET_STORE",
    tls=True,
    stale_after=10.0,  # choose a threshold appropriate for the robot's expected telemetry cadence
)
engine = Genesis()

try:
    connector.connect()
    while True:
        packet = connector.read(timeout=5.0)
        if packet is None:
            # No message arrived during this interval. This is not evidence
            # that the robot is healthy or that its sensors read zero.
            continue
        record, result = investigate_packet(
            packet, engine, connector_id=connector.connector_id
        )
        print(result)
finally:
    connector.disconnect()
```

Set `stale_after` to a positive number of seconds if you want `get_status()`
to report `DEGRADED` when no valid telemetry has arrived within that interval.
It uses local monotonic arrival time, not source timestamps. Leave it as `None`
when the expected message cadence is unknown. A valid new message restores
`CONNECTED`.

Use broker credentials restricted to read access to the required telemetry
topic. Do not hard-code real credentials in source control. Enable TLS where
the broker supports it. This connector intentionally does not implement a
robot command channel.

## 4. Provenance and safety boundaries

The packet records the MQTT topic and states that KORDEX has not independently
authenticated the physical source of the telemetry. Broker authentication can
help restrict access but does not prove that the underlying sensor values are
correct or that the named robot produced them. Keep broker addresses and
credentials private; do not expose the robot network directly to the public
internet.

Begin with a local test broker or simulated publisher, then use a supervised,
read-only trial with the robot owner's permission. Validate message cadence,
units, timestamps, stale-data behavior, and signal semantics before interpreting
investigation results. KORDEX's current analysis output is not a validated
robot-specific failure prediction and should not control equipment.

## 5. Targeted validation

From the GenesisLab project root, run the connector-focused tests:

```powershell
python -m unittest test_telemetry_connector_contract.py test_ros2_telemetry_adapter.py test_ros2_connector_bridge.py test_mqtt_telemetry_connector.py test_mqtt_connector_engine_integration.py test_mqtt_local_broker_integration.py test_connector_cross_transport_parity.py test_mqtt_paho_interoperability.py
```

`test_mqtt_local_broker_integration.py` starts a tiny, test-only MQTT 3.1.1
broker and client over a real local TCP socket. It exercises CONNECT, SUBSCRIBE,
PUBLISH, JSON decoding, provenance preservation, and the Genesis investigation
handoff without requiring a third-party broker package. The test fixture is
intentionally minimal and is not a production MQTT implementation.

## 6. Current scope

- Implemented: optional MQTT subscriber, JSON payload validation, packet
  creation, signal discovery after messages arrive, connection status, and
  integration with the existing `Genesis.investigate()` pipeline.
- Targeted tests cover: contract behavior, ROS 2 payload translation, MQTT
  payload validation, local MQTT protocol flow, provenance/units, and common
  engine behavior across ROS 2 and MQTT packet shapes.
- Not validated here: interoperability with the production `paho-mqtt` client
  against a vendor/real broker, any particular robot vendor, high-rate delivery,
  production reconnection behavior, or failure-prediction accuracy. Those
  require separate, purpose-driven experiments.
