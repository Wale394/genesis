import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from genesis_field_agent import GenesisFieldAgent
from genesis_field_agent_config import GenesisFieldAgentConfig
from ros2_telemetry_adapter import ROS2TelemetryAdapter


def diagnostic(values, sec=1):
    return {
        "header": {"stamp": {"sec": sec, "nanosec": 0}},
        "status": [{
            "name": "robot/diagnostics",
            "values": [{"key": key, "value": value} for key, value in values.items()],
        }],
    }


class GenesisFieldAgentTests(unittest.TestCase):
    def config(self, **overrides):
        options = {
            "session_id": "FIELD-TEST",
            "robot_id": "R1",
            "manufacturer": "ABB",
            "robot_type": "AMR",
            "field_units": {
                "motor_temperature": "C",
                "battery_voltage": "V",
            },
        }
        options.update(overrides)
        return GenesisFieldAgentConfig(**options)

    def test_agent_initialization(self):
        agent = GenesisFieldAgent(self.config())
        session = agent.get_session()
        self.assertEqual(session["schema_version"], "0.1")
        self.assertEqual(session["session"]["robot"]["robot_id"], "R1")

    def test_configuration_serialization_round_trip(self):
        config = self.config()
        encoded = json.dumps(config.to_dict())
        restored = GenesisFieldAgentConfig.from_dict(json.loads(encoded))
        self.assertEqual(restored.to_dict(), config.to_dict())

    def test_diagnostic_message_ingestion_and_adapter_usage(self):
        with patch("genesis_field_agent.ROS2TelemetryAdapter") as adapter_type:
            adapter = adapter_type.return_value
            adapter.ingest.return_value = {
                "telemetry": {"motor_temperature": 52.4},
                "source_metadata": {"source": "ros2"},
                "limitations": [],
            }
            agent = GenesisFieldAgent(self.config())
            result = agent.ingest_diagnostics(diagnostic({"motor_temperature": "52.4"}))
            adapter_type.assert_called_once()
            adapter.ingest.assert_called_once()
            self.assertEqual(result["telemetry"]["motor_temperature"], 52.4)

    def test_normalized_telemetry_source_metadata_and_limitations_are_recorded(self):
        agent = GenesisFieldAgent(self.config())
        agent.ingest_diagnostics(diagnostic({"motor_temperature": "52.4 C", "unknown": "x"}))
        observation = agent.get_session()["observations"][0]
        self.assertEqual(observation["telemetry"]["motor_temperature"], 52.4)
        self.assertEqual(observation["source_metadata"]["source"], "ros2")
        self.assertTrue(any("Unmapped diagnostic keys" in item for item in observation["limitations"]))

    def test_multiple_observations_remain_chronological(self):
        agent = GenesisFieldAgent(self.config())
        agent.ingest_diagnostics(diagnostic({"motor_temperature": "50 C"}, sec=1))
        agent.ingest_diagnostics(diagnostic({"motor_temperature": "51 C"}, sec=2))
        observations = agent.get_session()["observations"]
        self.assertEqual([item["telemetry"]["time_step"] for item in observations], [1, 2])

    def test_genesis_result_is_kept_separate_and_preserved(self):
        genesis = Mock()
        genesis.investigate.return_value = {"reliability_state": {"current": "WATCH"}}
        agent = GenesisFieldAgent(self.config(genesis_analysis_enabled=True), genesis_api=genesis)
        agent.ingest_diagnostics(diagnostic({"motor_temperature": "52 C"}))
        session = agent.get_session()
        self.assertIn("motor_temperature", session["observations"][0]["telemetry"])
        self.assertEqual(session["genesis_results"][0]["result"]["reliability_state"]["current"], "WATCH")
        self.assertEqual(session["genesis_results"][0]["observation_index"], 0)
        genesis.investigate.assert_called_once()

    def test_operates_without_ros2_installed(self):
        self.assertNotIn("rclpy", ROS2TelemetryAdapter.__module__)
        agent = GenesisFieldAgent(self.config())
        agent.ingest_diagnostics(diagnostic({"motor_temperature": "52 C"}))
        self.assertEqual(len(agent.get_session()["observations"]), 1)

    def test_missing_optional_telemetry_is_not_fabricated(self):
        agent = GenesisFieldAgent(self.config())
        agent.ingest_diagnostics(diagnostic({"motor_temperature": "52 C"}))
        telemetry = agent.get_session()["observations"][0]["telemetry"]
        self.assertNotIn("battery_voltage", telemetry)
        self.assertNotIn("battery_level", telemetry)

    def test_malformed_input_has_clear_error(self):
        agent = GenesisFieldAgent(self.config())
        with self.assertRaisesRegex(ValueError, "DiagnosticArray"):
            agent.ingest_diagnostics({"not_status": []})

    def test_session_is_json_serializable_and_saved(self):
        agent = GenesisFieldAgent(self.config())
        agent.ingest_diagnostics(diagnostic({"motor_temperature": "52 C"}))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            saved = agent.save_session(path)
            self.assertTrue(Path(saved).is_file())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), agent.get_session())

    def test_session_schema_is_valid_json_schema_document(self):
        schema_path = Path(__file__).with_name("genesis_field_session_schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(set(schema["required"]), {"schema_version", "session", "observations", "genesis_results"})
        self.assertEqual(schema["properties"]["observations"]["type"], "array")
        try:
            from jsonschema.validators import validator_for
        except ImportError:
            # Keep the test dependency-free; a standards validator is optional.
            self.assertEqual(schema["type"], "object")
        else:
            validator_for(schema).check_schema(schema)

    def test_agent_exposes_no_robot_control_api(self):
        public_methods = {
            name for name in dir(GenesisFieldAgent)
            if not name.startswith("_") and callable(getattr(GenesisFieldAgent, name))
        }
        self.assertEqual(public_methods, {"ingest_diagnostics", "get_session", "save_session"})
        self.assertFalse(hasattr(GenesisFieldAgent, "publish_command"))
        self.assertFalse(hasattr(GenesisFieldAgent, "control_robot"))

    def test_existing_genesis_behavior_is_unchanged(self):
        # The field agent passes the adapter snapshot through the existing public API.
        from genesis import Genesis
        genesis = Genesis()
        agent = GenesisFieldAgent(self.config(genesis_analysis_enabled=True), genesis_api=genesis)
        agent.ingest_diagnostics(diagnostic({"motor_temperature": "48 C"}))
        result = agent.get_session()["genesis_results"][0]["result"]
        self.assertIn("reliability_state", result)
        self.assertEqual(result["robot"]["robot_id"], "R1")


if __name__ == "__main__":
    unittest.main()

