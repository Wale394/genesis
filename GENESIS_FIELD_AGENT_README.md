# Genesis Field Agent v0.1

## What it is

A read-only telemetry and field-session agent for robotics creators evaluating Genesis. It translates recorded or ROS-like diagnostics, records available telemetry with source metadata and limitations, and can optionally call the existing Genesis public API.

## What it does

- Uses the existing `ROS2TelemetryAdapter` for diagnostic translation and unit normalization.
- Preserves each chronological observation, adapter metadata, and limitations in a JSON session.
- Optionally stores a separate Genesis investigation result for each observation.

## What it does not do

It does not control a robot, publish commands, configure navigation, actuate hardware, or execute Genesis recommendations. It does not determine that ROS 2 is installed or start a ROS 2 subscriber.

## Requirements

### Current offline/recorded mode

- Python
- The Genesis source files in this repository
- JSON configuration and recorded ROS-like diagnostic messages
- ROS 2 is **not required**

### Future live ROS 2 runtime

A ROS 2 environment and diagnostic topic access will be needed. A thin `rclpy` subscriber must be written to read diagnostics and pass messages to `GenesisFieldAgent.ingest_diagnostics`. That subscriber is not included in v0.1.

## Basic workflow

1. Configure the session and robot identity in `config.example.json`.
2. Start offline processing with the command below, or construct `GenesisFieldAgent` in an application.
3. Provide recorded diagnostic messages; for a future live runtime, the subscriber will call `ingest_diagnostics`.
4. Operate the robot normally under its existing controller.
5. Stop the agent/session.
6. Save and retain the JSON session.
7. Analyze the recorded session with Genesis.

## Offline recorded-message usage

Input JSON may be one DiagnosticArray-like object or an array of them. The adapter expects each message to expose `status`, each status to expose `name` and `values`, and each value to expose `key` and `value` (JSON objects with these property names also work). Use explicit unit companion keys or configure `field_units`.

From the repository root:

```powershell
python genesis_field_agent.py --config config.example.json --input recorded_diagnostics.json --output field-session.json
```

To use the Python API:

```python
from genesis_field_agent import GenesisFieldAgent
from genesis_field_agent_config import GenesisFieldAgentConfig

config = GenesisFieldAgentConfig(
    session_id="FIELD-001",
    robot_id="R1",
    manufacturer="ABB",
    robot_type="AMR",
    field_units={"motor_temperature": "C", "battery_voltage": "V"},
    output_path="field-session.json",
)
agent = GenesisFieldAgent(config)
observation = agent.ingest_diagnostics(recorded_message)
agent.save_session()
```

Genesis analysis is off by default. Set `genesis_analysis_enabled` to `true` to call `Genesis.investigate` for each observation. The output is stored under `genesis_results` separately from `observations`.

## Session format

The session follows [genesis_field_session_schema.json](genesis_field_session_schema.json). Unknown telemetry is omitted rather than fabricated. Adapter limitations and source metadata are retained. Session output is JSON; no durable database is included.

## Intended distribution layout

The intended future distribution is:

```text
genesis-field-agent/
├── README.md                         # this document in the package
├── SAFETY.md                         # GENESIS_FIELD_AGENT_SAFETY.md in the package
├── config.example.json
├── genesis_field_agent.py
├── genesis_field_agent_config.py
├── ros2_telemetry_adapter.py         # included as a single source dependency
└── session_schema.json               # genesis_field_session_schema.json
```

This repository does not yet contain an installable package/installer. The layout above is a packaging target; source files are not copied into a second directory.

## Safety

Read [GENESIS_FIELD_AGENT_SAFETY.md](GENESIS_FIELD_AGENT_SAFETY.md) before connecting telemetry from a robot.

