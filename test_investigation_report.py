"""Tests for the deterministic, presentation-only investigation report."""

from copy import deepcopy
import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from demo_genesis_investigation import demo_telemetry_records
from genesis import Genesis
from genesis_cli import main as genesis_cli_main, run_controlled_investigation
from investigation_report import (
    build_field_session_report,
    build_investigation_report,
    render_investigation_report,
)


def controlled():
    return run_controlled_investigation()


class InvestigationReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.critical_result = controlled()
        cls.critical_report = build_investigation_report(cls.critical_result)
        cls.critical_text = render_investigation_report(cls.critical_report)

    def test_healthy_investigation_has_only_existing_observation_and_state(self):
        result = Genesis().investigate(demo_telemetry_records(count=1)[0])
        report = build_investigation_report(result)
        self.assertEqual(report["robot"]["robot_id"], "R004")
        self.assertEqual(report["investigation"]["state"], result["reliability_state"]["current"])
        self.assertTrue(report["what_happened"])
        self.assertFalse(report["observed_patterns"])

    def test_critical_thermal_report_exposes_existing_pattern_and_signals(self):
        self.assertEqual(self.critical_report["investigation"]["state"], "CRITICAL")
        self.assertTrue(self.critical_report["observed_patterns"])
        signals = {item["signal"] for item in self.critical_report["engineering_signals"]}
        self.assertIn("critical_motor_temperature", signals)
        self.assertIn("critical_thermal_rise", signals)
        self.assertIn("42°C → 44°C → 47°C → 52°C → 58°C → 61°C", self.critical_text)
        assessment_text = " ".join(item["statement"] for item in self.critical_report["assessment"])
        self.assertIn("above the range of comparable peers", assessment_text)

    def test_ml_unavailable_is_reported_without_probability(self):
        report = self.critical_report
        self.assertFalse(report["ml_inference"]["prediction_available"])
        self.assertIsNone(report["ml_inference"]["probability"])
        self.assertIn("Unavailable", render_investigation_report(report))
        self.assertIn("no fitted model artifact", render_investigation_report(report).lower())

    def test_ml_available_preserves_existing_probability(self):
        result = deepcopy(self.critical_result)
        result["ml_inference"].update({"prediction_available": True, "probability": 0.82,
                                       "model_prediction": 1})
        report = build_investigation_report(result)
        self.assertEqual(report["ml_inference"]["probability"], 0.82)
        self.assertIn("Failure probability: 0.82", render_investigation_report(report))

    def test_historical_memory_matches_are_preserved(self):
        self.assertEqual(len(self.critical_report["historical_context"]), 2)
        match = self.critical_report["historical_context"][0]
        self.assertIn("similarity_reasons", match)
        self.assertIn("recommendation", match)
        self.assertIn("human_action", match)
        self.assertIn("outcome", match)
        self.assertIn("2 similar incident(s) found", self.critical_text)

    def test_fleet_context_and_nonproof_limitation_are_preserved(self):
        fleet = self.critical_report["fleet_context"]
        self.assertEqual(fleet["comparable_robot_count"], 3)
        self.assertEqual(fleet["metrics"]["motor_temperature"]["status"], "OUTLIER")
        self.assertIn("current_robot=61.0", render_investigation_report(self.critical_report))
        self.assertIn("Fleet comparison is contextual evidence and is not proof of failure.",
                      fleet["limitations"])

    def test_missing_telemetry_remains_in_unknowns(self):
        result = Genesis().investigate({
            "robot_id": "PARTIAL-1", "time_step": 1, "motor_temperature": 40.0,
        })
        report = build_investigation_report(result)
        unknown = " ".join(report["unknowns_and_limitations"])
        self.assertIn("Not observed", unknown)
        self.assertIn("battery_temperature", unknown)

    def test_sampling_limitation_is_visible(self):
        result = Genesis().investigate([
            {"robot_id": "SAMP-1", "time_step": 1, "motor_temperature": 40},
            {"robot_id": "SAMP-1", "time_step": 4, "motor_temperature": 42},
        ])
        report = build_investigation_report(result)
        self.assertTrue(any("sampling cadence is unspecified" in item.lower()
                            for item in report["unknowns_and_limitations"]))

    def test_human_action_pending_is_not_invented(self):
        self.assertEqual(self.critical_report["human_action"]["status"], "PENDING")
        self.assertIn("HUMAN ACTION\n--------------------------------------------------\n- Pending", self.critical_text)

    def test_completed_action_and_outcome_are_preserved(self):
        result = deepcopy(self.critical_result)
        result["human_action"] = {"status": "RECORDED", "items": ["Technician inspected motor assembly."]}
        result["outcome"] = {"status": "RESOLVED", "resolved": True,
                              "details": {"description": "Bearing replaced."}}
        report = build_investigation_report(result)
        rendered = render_investigation_report(report)
        self.assertEqual(report["human_action"]["items"], ["Technician inspected motor assembly."])
        self.assertIn("Technician inspected motor assembly.", rendered)
        self.assertIn("Bearing replaced", rendered)

    def test_unresolved_evidence_tension_is_not_resolved_by_report(self):
        result = deepcopy(self.critical_result)
        contradiction = {
            "contradiction_id": "test-tension", "resolved": False,
            "statement": "Existing sources disagree.", "sources": ["source-a", "source-b"],
        }
        result["evidence_synthesis"]["contradictions"] = [contradiction]
        report = build_investigation_report(result)
        self.assertEqual(report["evidence_tension"], [contradiction])
        self.assertTrue(any("cannot resolve" in item["statement"].lower()
                            for item in report["assessment"]))
        self.assertIn("Genesis cannot resolve this evidence tension", render_investigation_report(report))

    def test_report_does_not_fabricate_diagnosis_or_cause(self):
        self.assertIsNone(self.critical_report["ml_inference"].get("diagnosis"))
        self.assertFalse(any(item.get("kind") == "diagnosis_inference"
                             for item in self.critical_report["assessment"]))
        self.assertNotIn("bearing is failing", self.critical_text.lower())
        self.assertIn("RecommendationEngine", self.critical_report["recommendation"][0]["source"])

    def test_report_is_json_serializable(self):
        encoded = json.dumps(self.critical_report, ensure_ascii=False, allow_nan=False)
        self.assertEqual(json.loads(encoded), self.critical_report)

    def test_rendering_is_deterministic(self):
        self.assertEqual(self.critical_text, render_investigation_report(self.critical_report))

    def test_report_generation_does_not_mutate_genesis_result(self):
        result = controlled()
        before = deepcopy(result)
        build_investigation_report(result)
        self.assertEqual(result, before)

    def test_evidence_timeline_uses_existing_chronological_events(self):
        timeline = self.critical_report["evidence_timeline"]
        self.assertEqual(timeline["event_count"], len(timeline["events"]))
        self.assertEqual(timeline["time_basis"], "source time_step")
        self.assertEqual([event["time_step"] for event in timeline["events"]],
                         sorted(event["time_step"] for event in timeline["events"]))

    def test_genesis_cli_report_mode_preserves_existing_json_mode(self):
        output = StringIO()
        with redirect_stdout(output):
            genesis_cli_main(["--report"])
        self.assertIn("GENESIS INVESTIGATION REPORT", output.getvalue())
        with redirect_stdout(StringIO()):
            genesis_cli_main(["--json"])

    def test_field_session_report_combines_existing_observations_and_timelines(self):
        session = {
            "session": {"session_id": "S-1", "sampling_context": None,
                        "robot": {"robot_id": "FIELD-1"}},
            "observations": [
                {"telemetry": {"time_step": 1, "motor_temperature": 40}},
                {"telemetry": {"time_step": 2, "motor_temperature": 42}},
            ],
            "genesis_results": [
                {"result": {**deepcopy(self.critical_result), "evidence_timeline": {
                    "event_count": 1, "events": [{"time_step": 1, "event_type": "observation",
                                                   "description": "Observed first sample."}],
                }}},
                {"result": {**deepcopy(self.critical_result), "evidence_timeline": {
                    "event_count": 1, "events": [{"time_step": 2, "event_type": "observation",
                                                   "description": "Observed second sample."}],
                }}},
            ],
        }
        report = build_field_session_report(session)
        self.assertIn("40°C → 42°C", render_investigation_report(report))
        self.assertEqual(report["evidence_timeline"]["event_count"], 2)
        self.assertEqual(report["field_session"]["session_id"], "S-1")


if __name__ == "__main__":
    unittest.main()
