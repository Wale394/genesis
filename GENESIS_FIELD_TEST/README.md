# Genesis Field Test — recorded telemetry package

This is a small, self-contained external test package for processing a recorded ROS-like diagnostic stream with Genesis. It includes the actual Field Agent, adapter, public Genesis facade, and the local Genesis runtime modules needed by that analysis path. It does not contain the Genesis repository, model-training pipeline, simulator, datasets, or experimental validation code.

## What it does

The package reads a JSON file containing one DiagnosticArray-like object or a list of them, translates supported diagnostic keys and units through `ROS2TelemetryAdapter`, records normalized observations and source metadata, sends each snapshot through the existing `Genesis.investigate` API, and saves one JSON session with the separate Genesis results.

## What it does not do

- It does not connect to a live ROS 2 graph or include an `rclpy` subscriber.
- It does not control a robot, publish commands, modify navigation/configuration, or actuate hardware.
- It does not include a fitted risk/diagnosis model. ML inference remains unavailable unless a future integration supplies a supported artifact.
- It does not include an installer or production deployment service.

## Prerequisites

- Python 3.10 or newer (the included code uses only the Python standard library for recorded mode).
- No ROS 2 installation is required for this offline example.
- No third-party Python packages are required by this package; `requirements.txt` is intentionally empty of package entries.

## Configure a robot

Edit `config.example.json` or make a copy. Set `session_id`, `robot_id`, `manufacturer`, and `robot_type`. Set `field_units` only for numeric telemetry that may be sent without units. Source values may also carry explicit units (for example `52 C`); adapter unit validation still applies. Map vendor diagnostic keys using `telemetry_mapping` when needed. Keep `genesis_analysis_enabled` true to run the existing Genesis public API.

Missing or unsupported telemetry is left absent and documented in observation limitations. Do not map a field to a different measurement merely to make it available.

### Optional sampling context

Sampling context is optional. Genesis does not assume a universal robot telemetry rate because diagnostic streams may be event-driven or configured differently by each robot owner. To describe an expected cadence, set `sampling_context` in the configuration:

```json
{
  "sampling_context": {
    "expected_interval": 1.0,
    "allowed_jitter": 0.2
  }
}
```

Both values are in seconds. `expected_interval` must be greater than zero and `allowed_jitter` must be nonnegative. Set `sampling_context` to `null` or omit it when cadence is unknown. With no context, Genesis reports observed timestamp intervals but does not classify them as missing telemetry. With context, an interval above `expected_interval + allowed_jitter` is marked `POSSIBLE_DATA_GAP`. That means the timestamps are farther apart than configured; it is not proof that any observations were lost.

## Process recorded diagnostics

From this folder, use the included example:

```powershell
python genesis_field_agent.py --config config.example.json --input examples/recorded_diagnostics_example.json --output field-session.json
```

The input is an object with a `messages` array of ROS-like `DiagnosticArray` records. Each message uses `header.stamp`, `status[].name`, and `status[].values[]` with `key` and `value`, matching the existing adapter's supported duck-typed shape.

## Output

The command writes `field-session.json` (or the path passed with `--output`) using `genesis_field_session_schema.json`. It contains chronological normalized telemetry with source metadata and limitations, and a separate `genesis_results` list. Each result includes the normal public Genesis investigation structure, including evidence synthesis, telemetry capability discovery, and available limitations. The example has no fitted model artifact, so it does not invent ML probabilities.

To render the saved session as an engineer-readable report, run:

```powershell
python investigation_report.py --input field-session.json
```

Add `--output investigation-report.txt` to save the plain-text report. The report uses the latest existing Genesis result and combines only the already-recorded per-observation timeline events. It does not run additional inference or require ML.

## Safety / read-only limitations

The included path accepts messages and writes a local session file. It has no robot-control methods or ROS publishing code. It does not grant or enforce operating-system permissions: run it with telemetry read access only, leave the robot under its existing controller, and ensure the agent process can be stopped independently. Review the telemetry mapping and units before interpreting a session. This package has not been certified or field-validated on hardware.

## Package contents and runtime closure

The root Python modules include the exact local import closure required by `GenesisFieldAgent` when Genesis analysis is enabled. These are source modules from the project, not replacements. `requirements.txt` records that the recorded runtime has no external Python dependencies. `examples/recorded_diagnostics_example.json` requires no robot or ROS installation.

