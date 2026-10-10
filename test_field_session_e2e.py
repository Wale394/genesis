"""Deterministic recorded diagnostics → Field Agent → Genesis integration test."""

import json
from pathlib import Path
import unittest

from genesis_field_agent import GenesisFieldAgent, _load_recorded_messages
from genesis_field_agent_config import GenesisFieldAgentConfig
from investigation_report import build_field_session_report, render_investigation_report


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"
CONFIG_PATH = FIXTURES / "field_session_r001_config.json"
MESSAGES_PATH = FIXTURES / "field_session_r001_diagnostics.json"
OUTPUT_PATH = ROOT / "field-session-e2e.json"


class FieldSessionEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = GenesisFieldAgentConfig.from_dict(
            json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        )
        config.output_path = str(OUTPUT_PATH)
        cls.messages = _load_recorded_messages(MESSAGES_PATH)
        cls.agent = GenesisFieldAgent(config)
        for message in cls.messages:
            cls.agent.ingest_diagnostics(message)
        cls.agent.save_session()
        cls.session = cls.agent.get_session()
        cls.saved_session = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))

    def test_recorded_session_runs_end_to_end_and_saves_structured_evidence(self):
        session = self.session
        self.assertEqual(session["session"]["robot"], {
            "robot_id": "FIELD-R001", "manufacturer": "ABB", "robot_type": "AMR",
        })
        self.assertEqual(len(session["observations"]), 10)
        self.assertEqual(len(session["genesis_results"]), 10)

        observed_temperatures = [
            item["telemetry"]["motor_temperature"] for item in session["observations"]
        ]
        self.assertEqual(observed_temperatures, [42.0, 43.0, 44.0, 46.0, 48.0, 51.0, 53.0, 56.0, 59.0, 61.0])
        timestamps = [item["telemetry"]["time_step"] for item in session["observations"]]
        self.assertEqual(timestamps, sorted(timestamps))

        first_observation = session["observations"][0]
        self.assertEqual(first_observation["source_metadata"]["source"], "ros2")
        self.assertEqual(first_observation["source_metadata"]["diagnostic_components"], ["drive/diagnostics"])
        self.assertEqual(first_observation["source_metadata"]["units"]["motor_temperature"], "C")

        self.assertEqual(
            [entry["observation_index"] for entry in session["genesis_results"]],
            list(range(10)),
        )
        final = session["genesis_results"][-1]["result"]
        self.assertEqual(final["robot"]["robot_id"], "FIELD-R001")
        self.assertEqual(final["capability_discovery"]["observation_count"], 10)
        self.assertEqual(
            final["capability_discovery"]["robot_identity"]["robot_id"],
            "FIELD-R001",
        )
        self.assertEqual(final["processing"]["observation_count"], 1)
        self.assertIn("reliability_state", final)
        self.assertIn("observations", final)
        self.assertTrue(final["observations"])
        self.assertIn("temporal_evidence", final)
        self.assertIn("engineering_signals", final)
        self.assertIn("ml_inference", final)
        self.assertIn("evidence_synthesis", final)
        self.assertIn("limitations", final)
        self.assertIn("recommendation", final)
        self.assertIn("human_action", final)
        self.assertIn("outcome", final)

        synthesis = final["evidence_synthesis"]
        self.assertTrue(synthesis["observations"])
        self.assertTrue(synthesis["pattern_evidence"])
        self.assertTrue(any(
            item.get("evidence_type") == "PATTERN"
            and item.get("source") == "telemetry_pattern_engine"
            for item in synthesis["pattern_evidence"]
        ))
        self.assertIn("engineering_evidence", synthesis)
        self.assertIn("ml_evidence", synthesis)
        self.assertIn("fleet_evidence", synthesis)
        self.assertIn("historical_evidence", synthesis)
        self.assertIn("quality_evidence", synthesis)
        self.assertIn("missing_evidence", synthesis)
        self.assertIn("recommendation", synthesis)
        self.assertEqual(synthesis["pattern_analysis"]["observations_analyzed"], 10)
        self.assertEqual(final["baseline_visibility"]["status"], "ELIGIBILITY_UNKNOWN")
        self.assertEqual(final["baseline_visibility"]["eligible_records"], 0)
        self.assertEqual(final["baseline_visibility"]["required_records"], 10)
        self.assertEqual(final["baseline_visibility"]["observed_records"], 9)
        self.assertEqual(final["historical_comparison"]["status"], "AVAILABLE")
        self.assertTrue(any(
            "no explicit eligibility decisions were supplied" in item.lower()
            for item in final["limitations"]
        ))
        self.assertEqual(final["reliability_state"]["current"], "CRITICAL")
        self.assertFalse(final["ml_inference"].get("prediction_available", False))
        self.assertIsNone(final["ml_inference"].get("diagnosis"))
        self.assertEqual(
            final["recommendation"]["recommendation"],
            "Reduce robot workload and perform a reliability inspection.",
        )
        self.assertEqual(final["incident"]["status"], "ACTIVE")

        report = build_field_session_report(session)
        rendered_report = render_investigation_report(report)
        self.assertIn("HISTORICAL COMPARISON", rendered_report)
        self.assertIn("Baseline status: ELIGIBILITY_UNKNOWN", rendered_report)
        self.assertIn("0 / 10 required", rendered_report)
        self.assertIn("No explicit eligibility decisions were supplied.", rendered_report)

        # This Genesis facade has no fitted model artifact; no model result is fabricated.
        self.assertFalse(final["ml_inference"].get("prediction_available", False))
        self.assertIsNone(final["ml_inference"].get("probability"))

        # Telemetry and analysis are separate session collections.
        self.assertNotIn("evidence_synthesis", session["observations"][0])
        self.assertNotIn("telemetry", session["genesis_results"][0]["result"])
        self.assertEqual(self.saved_session, session)
        self.assertEqual(self.saved_session["schema_version"], "0.1")

        # Validate the schema's essential structure locally; no jsonschema dependency is installed.
        schema = json.loads((ROOT / "genesis_field_session_schema.json").read_text(encoding="utf-8"))
        self.assertTrue(set(schema["required"]).issubset(self.saved_session))
        self.assertEqual(self.saved_session["session"]["source"], "ros2")
        self.assertTrue(all(
            {"telemetry", "source_metadata", "limitations"}.issubset(observation)
            for observation in self.saved_session["observations"]
        ))
        self.assertTrue(all(
            {"observation_index", "result"}.issubset(result)
            for result in self.saved_session["genesis_results"]
        ))
        json.dumps(self.saved_session, allow_nan=False)

        public_methods = {
            name for name in dir(GenesisFieldAgent)
            if not name.startswith("_") and callable(getattr(GenesisFieldAgent, name))
        }
        self.assertEqual(public_methods, {"ingest_diagnostics", "get_session", "save_session"})
        self.assertFalse(hasattr(self.agent, "publish_command"))
        self.assertFalse(hasattr(self.agent, "control_robot"))


if __name__ == "__main__":
    unittest.main()

