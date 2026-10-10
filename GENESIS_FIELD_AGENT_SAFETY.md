# Genesis Field Agent v0.1 Safety Boundary

Genesis Field Agent v0.1 is a **read-only telemetry ingestion and session-recording component**. It receives ROS-like diagnostic messages through `ROS2TelemetryAdapter`, records the telemetry and adapter metadata, and can optionally pass each snapshot to the existing public `Genesis.investigate` API.

The Field Agent has no robot-control interface. Its implementation does not publish robot messages or invoke control APIs. In particular, it does not publish `/cmd_vel`, motor commands, actuator commands, or navigation commands. It does not modify robot configuration, navigation, or actuators, execute recommendations, or call emergency-stop APIs. It records any analysis result separately from the telemetry observation.

## Tester checks before a session

- Keep the robot under its existing controller and operate it through the normal control path.
- Grant the agent read-only access to the telemetry/diagnostic source.
- Do not grant the agent write or robot-control permissions.
- Confirm the creator can stop the agent process independently of the robot controller.
- Confirm the configured diagnostic field mappings and units match the telemetry source. Missing or invalid fields should remain unavailable and be represented in limitations.

This document describes the code boundary in this v0.1 component. It is not a claim that a particular deployment host, ROS graph, permissions system, or robot has been independently audited.
