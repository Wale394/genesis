import unittest
from pathlib import Path

from genesis_cli import _operator_report, run_controlled_investigation
from recommendation_engine import RecommendationEngine


class GenesisCliPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_controlled_investigation()
        cls.report = _operator_report(cls.result)

    def test_01_recommendation_matches_existing_engine_rule(self):
        expected = RecommendationEngine().recommend(
            {"probability": self.result["ml_inference"]["probability"]},
            diagnosis_result=None,
            state=self.result["reliability_state"]["current"],
            observation_quality=self.result["observation_quality"],
        )
        self.assertEqual(self.result["recommendation"], expected)
        self.assertEqual(
            expected["recommendation"],
            "Reduce robot workload and perform a reliability inspection.",
        )

    def test_02_recommendation_is_not_hardcoded_in_cli(self):
        source = Path(__file__).with_name("genesis_cli.py").read_text(encoding="utf-8")
        self.assertNotIn("Reduce robot workload and perform a reliability inspection.", source)
        self.assertIn('recommendation.get("recommendation")', source)

    def test_03_structured_result_retains_complete_sections(self):
        required = {
            "robot", "reliability_state", "incident", "observation_quality",
            "observations", "temporal_evidence", "engineering_signals",
            "ml_inference", "fleet_context", "historical_memory",
            "evidence_synthesis", "recommendation", "human_action", "outcome",
            "limitations", "processing",
        }
        self.assertTrue(required.issubset(self.result))

    def test_04_cli_contains_robot_identity(self):
        self.assertIn("R004 | ABB AMR", self.report)

    def test_05_cli_contains_reliability_state(self):
        self.assertIn("RELIABILITY STATE\nCRITICAL", self.report)

    def test_06_cli_contains_engineering_evidence(self):
        self.assertIn("Critical motor temperature", self.report)
        self.assertIn("Critical thermal rise", self.report)

    def test_07_cli_contains_fleet_evidence(self):
        self.assertIn("Peer mean: 43°C", self.report)
        self.assertIn("Peer range: 42–44°C", self.report)
        self.assertIn("R004 is an outlier", self.report)
        self.assertIn("Context only — not proof of failure", self.report)

    def test_08_cli_contains_historical_evidence(self):
        self.assertIn("2 similar incidents found", self.report)

    def test_09_cli_contains_ml_availability(self):
        self.assertIn("Unavailable — No fitted model artifact available", self.report)

    def test_10_cli_contains_observation_quality(self):
        self.assertIn("Thermal: AVAILABLE", self.report)
        self.assertIn("Battery: AVAILABLE", self.report)
        self.assertIn("Workload: AVAILABLE", self.report)

    def test_11_cli_contains_missing_evidence(self):
        section = self.report.split("WHAT GENESIS DOES NOT KNOW", 1)[1].split("RECOMMENDATION", 1)[0]
        self.assertIn("model artifact", section)
        self.assertIn("Diagnosis unavailable", section)
        self.assertIn("no recorded human action", section)
        self.assertIn("outcome pending", section)

    def test_12_cli_contains_pipeline_recommendation(self):
        self.assertIn(self.result["recommendation"]["recommendation"], self.report)

    def test_13_cli_contains_human_action_status(self):
        self.assertIn("HUMAN ACTION\nPending", self.report)

    def test_14_cli_contains_outcome_status(self):
        self.assertIn("OUTCOME\nPending", self.report)

    def test_15_cli_does_not_dump_raw_temporal_features(self):
        self.assertNotIn("temperature_rate_3", self.report)
        self.assertNotIn("thermal_rise_rate_3", self.report)
        self.assertLess(len(self.report), 3000)

    def test_16_cli_preserves_pipeline_results_and_boundaries(self):
        self.assertEqual(self.result["reliability_state"]["current"], "CRITICAL")
        self.assertEqual(self.result["observation_quality"]["status"], "AVAILABLE")
        self.assertIsNone(self.result["ml_inference"]["probability"])
        self.assertEqual(self.result["fleet_context"]["comparable_robot_count"], 3)
        self.assertEqual(self.result["outcome"]["status"], "OUTCOME_PENDING")


if __name__ == "__main__":
    unittest.main()
