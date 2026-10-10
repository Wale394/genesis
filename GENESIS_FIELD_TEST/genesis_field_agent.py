"""Read-only ingestion and session recording for Genesis field telemetry.

This module has no ROS imports and exposes no robot-control interface. Live ROS
runtime code, when added, should pass diagnostic messages to ``ingest_diagnostics``.
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path

from genesis_field_agent_config import GenesisFieldAgentConfig
from ros2_telemetry_adapter import ROS2TelemetryAdapter


class GenesisFieldAgent:
    """Compose the telemetry adapter, optional public Genesis API, and session log."""

    def __init__(self, config, *, genesis_api=None):
        if isinstance(config, dict):
            config = GenesisFieldAgentConfig.from_dict(config)
        if not isinstance(config, GenesisFieldAgentConfig):
            raise ValueError("config must be a GenesisFieldAgentConfig or configuration object")
        self.config = config
        self._adapter = ROS2TelemetryAdapter(
            robot_id=config.robot_id,
            manufacturer=config.manufacturer,
            robot_type=config.robot_type,
            key_mappings=config.telemetry_mapping,
            field_units=config.field_units,
        )
        self._genesis = genesis_api
        if config.genesis_analysis_enabled and self._genesis is None:
            # Lazy import keeps offline ingestion independent of the Genesis
            # ML runtime and avoids importing the pipeline when analysis is off.
            from genesis import Genesis
            self._genesis = Genesis()
        self._session = {
            "schema_version": "0.1",
            "session": {
                "session_id": config.session_id,
                "robot": {
                    "robot_id": config.robot_id,
                    "manufacturer": config.manufacturer,
                    "robot_type": config.robot_type,
                },
                "source": "ros2",
                "sampling_context": deepcopy(config.sampling_context),
            },
            "observations": [],
            "genesis_results": [],
        }

    def ingest_diagnostics(self, message):
        """Translate one ROS-like diagnostic message, record it, and optionally analyze it."""
        snapshot = self._adapter.ingest(message)
        observation = {
            "telemetry": deepcopy(snapshot["telemetry"]),
            "source_metadata": deepcopy(snapshot.get("source_metadata") or {}),
            "limitations": list(snapshot.get("limitations") or []),
        }
        self._session["observations"].append(observation)
        if self._genesis is not None:
            result = self._genesis.investigate(
                snapshot, sampling_context=self.config.sampling_context
            )
            self._session["genesis_results"].append({
                "observation_index": len(self._session["observations"]) - 1,
                "result": deepcopy(result),
            })
        return deepcopy(observation)

    def get_session(self):
        """Return an independent copy of the complete session document."""
        return deepcopy(self._session)

    def save_session(self, path=None):
        """Write the JSON session to ``path`` or the configured output path."""
        destination = path or self.config.output_path
        if not destination:
            raise ValueError("session output path is required")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = json.dumps(
                self._session, ensure_ascii=False, indent=2, allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"field session is not JSON serializable: {exc}") from exc
        destination.write_text(payload + "\n", encoding="utf-8")
        return str(destination)


def _load_recorded_messages(path):
    source = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(source, dict):
        source = source.get("messages", source)
        if isinstance(source, dict):
            source = [source]
    if not isinstance(source, list):
        raise ValueError("recorded input must be a diagnostic message object or a list of messages")
    return source


def main(argv=None):
    parser = argparse.ArgumentParser(description="Process recorded ROS-like diagnostics offline.")
    parser.add_argument("--config", required=True, help="JSON Field Agent configuration")
    parser.add_argument("--input", required=True, help="JSON diagnostic message or message list")
    parser.add_argument("--output", help="Session output path (overrides config output_path)")
    args = parser.parse_args(argv)
    config_data = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.output:
        config_data["output_path"] = args.output
    config = GenesisFieldAgentConfig.from_dict(config_data)
    agent = GenesisFieldAgent(config)
    for message in _load_recorded_messages(args.input):
        agent.ingest_diagnostics(message)
    saved_path = agent.save_session()
    print(f"Saved Genesis field session: {saved_path}")


if __name__ == "__main__":
    main()

