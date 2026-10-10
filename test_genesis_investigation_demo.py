import json
import unittest

from demo_genesis_investigation import (
    ENGINEERING_SIGNAL,
    MODEL_UNAVAILABLE_REASON,
    _format_report,
    run_demo,
)


class GenesisInvestigationDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_demo()
        cls.explanation = cls.report["explanation"]
        cls.result = cls.report["critical_result"]

    def test_01_demo_runs_successfully(self):
        self.assertEqual(self.report["dataset"], "CONTROLLED SIMULATION")

    def test_02_demo_data_is_deterministic(self):
        again = run_demo()
        self.assertEqual(
            json.dumps(self.report, sort_keys=True),
            json.dumps(again, sort_keys=True),
        )

    def test_03_r004_is_present(self):
        self.assertEqual(self.explanation["identity"]["robot_id"], "R004")

    def test_04_robot_identity_is_abb_amr(self):
        identity = self.explanation["identity"]
        self.assertEqual((identity["manufacturer"], identity["robot_type"]), ("ABB", "AMR"))

    def test_05_peer_group_uses_abb_amr(self):
        self.assertEqual(
            self.explanation["fleet_peer_context"]["peer_group"],
            {"manufacturer": "ABB", "robot_type": "AMR"},
        )

    def test_06_three_comparable_peers_are_used(self):
        self.assertEqual(self.explanation["fleet_peer_context"]["comparable_robot_count"], 3)

    def test_07_kuka_robotic_arm_is_excluded(self):
        metric = self.explanation["fleet_peer_context"]["metrics"]["motor_temperature"]
        self.assertEqual(metric["peer_count"], 3)
        self.assertEqual(metric["peer_mean"], 43.0)
        self.assertEqual(metric["peer_minimum"], 42.0)
        self.assertEqual(metric["peer_maximum"], 44.0)

    def test_08_fleet_comparison_marks_contextual_outlier(self):
        metric = self.explanation["fleet_peer_context"]["metrics"]["motor_temperature"]
        self.assertEqual(metric["status"], "OUTLIER")
        self.assertEqual(metric["robot_value"], 61.0)

    def test_09_existing_critical_motor_signal_is_present(self):
        signals = [item["signal"] for item in self.result["risk"]["engineering"]["signals"]]
        self.assertIn(ENGINEERING_SIGNAL, signals)

    def test_10_existing_critical_thermal_rise_signal_is_present(self):
        signals = [item["signal"] for item in self.result["risk"]["engineering"]["signals"]]
        self.assertIn("critical_thermal_rise", signals)

    def test_11_observation_quality_is_actual_component_result(self):
        quality = self.explanation["observation_quality"]
        self.assertEqual(quality["overall"], self.result["observation_quality"]["status"])
        self.assertEqual(quality["thermal"], self.result["observation_quality"]["groups"]["thermal"]["status"])

    def test_12_historical_memory_has_two_seed_matches(self):
        self.assertEqual(self.explanation["historical_memory"]["match_count"], 2)

    def test_13_recommendation_comes_from_existing_pipeline_result(self):
        self.assertEqual(
            self.explanation["recommendation"]["text"],
            self.result["recommendation"]["recommendation"],
        )
        self.assertEqual(self.explanation["recommendation"]["status"], "AVAILABLE")

    def test_14_human_action_is_preserved(self):
        self.assertEqual(
            self.explanation["human_action"]["items"],
            ["Technician inspected motor assembly."],
        )

    def test_15_simulated_outcome_is_preserved_and_labeled(self):
        outcome = self.explanation["outcome"]
        self.assertEqual(outcome["status"], "RESOLVED")
        self.assertIn("SIMULATED DEMO OUTCOME", outcome["details"]["demo_label"])
        self.assertIn("bearing wear found", outcome["details"]["description"])

    def test_16_incident_lifecycle_reaches_recovery_and_closed(self):
        statuses = [item["incident_status"] for item in self.report["lifecycle"]]
        self.assertIn("NO_INCIDENT", statuses)
        self.assertIn("ACTIVE", statuses)
        self.assertIn("RECOVERING", statuses)
        self.assertEqual(statuses[-1], "CLOSED")
        self.assertEqual(self.report["incident"]["status"], "CLOSED")

    def test_17_closed_incident_is_in_reliability_memory(self):
        current_id = self.report["incident"]["incident_id"]
        entries = {entry["identity"]["incident_id"] for entry in self.report["memory_entries"]}
        self.assertIn(current_id, entries)

    def test_18_future_query_retrieves_new_incident(self):
        current_id = self.report["incident"]["incident_id"]
        ids = {item["incident_id"] for item in self.report["future_memory_context"]["incidents"]}
        self.assertIn(current_id, ids)

    def test_19_ml_inference_is_explicitly_unavailable_without_artifact(self):
        ml = self.explanation["ml_inference"]
        self.assertFalse(ml["prediction_available"])
        self.assertIsNone(ml["probability"])
        self.assertEqual(self.result["risk"]["unavailable_reason"], MODEL_UNAVAILABLE_REASON)

    def test_20_explanation_does_not_present_simulator_truth_as_evidence(self):
        forbidden = {
            "battery_health", "battery_stress", "degradation_level", "health",
            "initial_health", "failure_event", "failure_type", "recovery_event",
            "failure_type_label", "label",
        }

        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key
                    yield from keys(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    yield from keys(child)

        self.assertFalse(forbidden.intersection(keys(self.explanation)))

    def test_21_demo_calls_existing_incident_lifecycle_api(self):
        from pathlib import Path
        import demo_genesis_investigation

        source = Path(demo_genesis_investigation.__file__).read_text(encoding="utf-8")
        self.assertIn("incident_manager.mark_recovering", source)
        self.assertIn("incident_manager.close_incident", source)
        self.assertNotIn("incident.status =", source)

    def test_22_demo_does_not_define_replacement_thresholds(self):
        from pathlib import Path
        import demo_genesis_investigation

        source = Path(demo_genesis_investigation.__file__).read_text(encoding="utf-8")
        self.assertNotIn("critical_motor_temperature=", source)
        self.assertNotIn("critical_thermal_rise=", source)

    def test_23_report_keeps_evidence_sources_separated(self):
        categories = {
            item["evidence_type"]
            for item in self.explanation["evidence_synthesis"]["observations"]
            + self.explanation["evidence_synthesis"]["engineering_evidence"]
            + self.explanation["evidence_synthesis"]["fleet_evidence"]
            + self.explanation["evidence_synthesis"]["ml_evidence"]
            + self.explanation["evidence_synthesis"]["historical_evidence"]
        }
        self.assertTrue({"OBSERVATION", "ENGINEERING_SIGNAL", "FLEET_COMPARISON", "ML_INFERENCE", "HISTORICAL_COMPARISON"}.issubset(categories))

    def test_24_console_report_is_readable_and_labeled(self):
        output = _format_report(self.report)
        self.assertIn("DATASET: CONTROLLED SIMULATION", output)
        self.assertIn("GENESIS RELIABILITY INVESTIGATION", output)
        self.assertIn("INCIDENT CLOSED", output)
        self.assertIn("MEMORY FEEDBACK", output)


if __name__ == "__main__":
    unittest.main()
