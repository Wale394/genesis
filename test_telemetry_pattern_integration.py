import unittest

from decision_pipeline import DecisionPipeline
from evidence_synthesis import (
    ENGINEERING_SIGNAL,
    ML_INFERENCE,
    PATTERN,
    EvidenceSynthesis,
)
from evidence_engine import EvidenceEngine
from history import History
from incident_explanation import IncidentExplanation
from incident_manager import IncidentManager
from recommendation_engine import RecommendationEngine
from reliability_state import ReliabilityState
from telemetry_features import TelemetryFeatureBuilder
from telemetry_pattern_engine import TelemetryPatternEngine


def pattern_analysis(values, **extra_fields):
    records = [
        {"time_step": index, "motor_temperature": value, **{
            field: series[index] for field, series in extra_fields.items()
        }}
        for index, value in enumerate(values)
    ]
    return TelemetryPatternEngine().analyze(records)


def pattern_names(result):
    return {item["supporting_data"]["pattern"] for item in result["pattern_evidence"]}


def synthesis_inputs(**overrides):
    values = {
        "feature_record": {
            "robot_id": "P-1", "manufacturer": "Maker", "robot_type": "AMR",
            "time_step": 9, "motor_temperature": 61.0,
            "ambient_temperature": 25.0, "thermal_rise": 36.0,
            "battery_level": 70.0, "workload": 55.0,
        },
        "risk_result": {
            "probability": 0.82, "prediction": 1, "model_prediction": 1,
            "prediction_available": True, "fused_risk": "WARNING",
            "engineering": {"status": "signal_detected", "severity": "critical", "signals": [
                {"signal": "critical_motor_temperature", "severity": "critical",
                 "value": 61.0, "message": "Critical motor temperature signal detected."},
            ]},
        },
        "diagnosis": None,
        "recommendation": {},
        "incident": None,
        "comparison": {"status": "comparison_available", "metrics": {"temperature_difference": 5.0}},
        "baseline": {"status": "baseline_available", "metrics": {"average_motor_temperature": 45.0}},
        "fleet_context": {"status": "AVAILABLE", "metrics": {"motor_temperature": {
            "metric": "motor_temperature", "robot_value": 61.0, "peer_count": 3,
            "peer_mean": 43.0, "peer_minimum": 42.0, "peer_maximum": 44.0,
            "deviation": 18.0, "z_score": 18.0, "status": "OUTLIER",
            "pattern": "robot_specific", "interpretation": "Observed temperature is above peer range.",
        }}},
        "historical_memory": {"status": "AVAILABLE", "match_count": 1, "incidents": [{
            "incident_id": "INC-001", "similarity_reasons": ["same_robot_type"],
            "engineering_signals": [], "diagnosis": {"status": "UNAVAILABLE"},
            "recommendation": {"text": None}, "human_action": {"items": []},
            "outcome": {"status": "pending", "details": None},
        }]},
    }
    values.update(overrides)
    return values


class FakePredictor:
    def predict(self, _record):
        return {"probability": 0.05, "prediction": 0}


class ComparisonStub:
    def compare_to_history(self, _record, _history):
        return {}


class BaselineStub:
    def build_baseline(self, _history):
        return {}


def make_pipeline():
    return DecisionPipeline(
        FakePredictor(), None, RecommendationEngine(), ReliabilityState(),
        IncidentManager(History()), EvidenceEngine(), ComparisonStub(), BaselineStub(),
    )


def pipeline_records():
    builder = TelemetryFeatureBuilder()
    records = []
    for step in range(6):
        records.append(builder.build({
            "identity": {"robot_id": "PIPE-PATTERN", "manufacturer": "Maker", "robot_type": "AMR"},
            "telemetry": {
                "time_step": step, "motor_temperature": 40.0 + 0.4 * step,
                "ambient_temperature": 25.0 + 0.1 * step,
                "battery_level": 80.0 - 0.8 * step,
                "battery_voltage": 48.0 - 0.02 * step,
                "battery_current": 20.0 + 0.1 * step,
                "battery_temperature": 30.0 + 0.1 * step,
                "power_consumption": 800.0 + 10.0 * step,
                "voltage_drop": 0.0, "workload": 40.0 + 5.0 * step,
            },
        }))
    return records


class TelemetryPatternIntegrationTests(unittest.TestCase):
    def synthesize_patterns(self, analysis, **overrides):
        values = synthesis_inputs(**overrides)
        return EvidenceSynthesis().synthesize(**values, telemetry_patterns=analysis)

    def test_sustained_rise_is_pattern_evidence(self):
        analysis = pattern_analysis([40, 40.8, 41.6, 42.4, 43.2, 44])
        result = self.synthesize_patterns(analysis)
        self.assertIn("SUSTAINED_RISE", pattern_names(result))

    def test_volatile_rise_is_pattern_evidence(self):
        result = self.synthesize_patterns(pattern_analysis(
            [67.33, 65.98, 66.51, 68.83, 64.81, 64.26, 67.28, 67.26, 77.61, 68.09]
        ))
        self.assertIn("VOLATILE_RISE", pattern_names(result))

    def test_rapid_spike_is_pattern_evidence(self):
        result = self.synthesize_patterns(pattern_analysis([40, 40.5, 41, 41.5, 42, 50]))
        self.assertIn("RAPID_SPIKE", pattern_names(result))

    def test_no_detectable_pattern_does_not_create_pattern_evidence(self):
        result = self.synthesize_patterns(pattern_analysis([40] * 10))
        self.assertEqual(result["pattern_evidence"], [])
        self.assertEqual(result["summary"]["what_pattern_was_observed"], [])

    def test_pattern_and_critical_engineering_evidence_remain_separate(self):
        result = self.synthesize_patterns(
            pattern_analysis([40, 40.8, 41.6, 42.4, 43.2, 44])
        )
        pattern = result["pattern_evidence"][0]
        engineering = result["engineering_evidence"][0]
        self.assertEqual(pattern["evidence_type"], PATTERN)
        self.assertEqual(pattern["source"], "telemetry_pattern_engine")
        self.assertEqual(engineering["evidence_type"], ENGINEERING_SIGNAL)
        self.assertEqual(engineering["source"], "ReliabilitySignal")

    def test_pattern_and_high_ml_risk_remain_separate(self):
        result = self.synthesize_patterns(
            pattern_analysis([40, 40.8, 41.6, 42.4, 43.2, 44])
        )
        self.assertTrue(any(item["evidence_type"] == PATTERN for item in result["pattern_evidence"]))
        self.assertTrue(any(item["evidence_type"] == ML_INFERENCE for item in result["ml_evidence"]))
        self.assertEqual(result["ml_evidence"][0]["supporting_data"]["probability"], 0.82)

    def test_pipeline_pattern_does_not_change_state_or_create_incident(self):
        records = pipeline_records()
        active_pipeline = make_pipeline()
        active = active_pipeline.evaluate(records[5], historical_records=records[:5])
        self.assertTrue(active["evidence_synthesis"]["pattern_evidence"])
        self.assertIsNone(active["incident"])
        self.assertIsNone(active["diagnosis"])

        control_pipeline = make_pipeline()
        control_pipeline.telemetry_pattern_engine.analyze = lambda _records: {
            "status": "available", "window_size": 10,
            "observations_analyzed": 6, "patterns": [], "limitations": [],
        }
        control = control_pipeline.evaluate(records[5], historical_records=records[:5])
        self.assertEqual(active["state"], control["state"])
        self.assertEqual(active["risk"], control["risk"])
        self.assertEqual(active["incident"], control["incident"])

    def test_pattern_does_not_create_diagnosis_or_causal_claim(self):
        analysis = pattern_analysis([40, 40, 46, 43, 43, 49, 47, 47])
        result = EvidenceSynthesis().synthesize(
            feature_record={"robot_id": "P-1"},
            telemetry_patterns=analysis,
        )
        self.assertFalse(any(
            item["source"] == "telemetry_pattern_engine"
            for item in result["ml_evidence"]
        ))
        for item in result["pattern_evidence"]:
            self.assertIsNone(item["confidence"])
            self.assertEqual(item["source"], "telemetry_pattern_engine")
            self.assertNotIn("cause", item["supporting_data"])
            self.assertNotIn("diagnosis", item["supporting_data"])
            self.assertIn("does not establish diagnosis or cause", item["limitations"][0])
        report = IncidentExplanation.build(
            {"robot_id": "P-1", "diagnosis": None, "risk": {}},
            {"robot_id": "P-1"},
            evidence_synthesis=result,
        )
        self.assertEqual(report["pattern_evidence"], result["pattern_evidence"])
        self.assertIsNone(report["ml_inference"]["diagnosis"])
        self.assertFalse(any("cause" in item for item in report["pattern_evidence"]))

    def test_existing_evidence_sources_still_appear(self):
        result = self.synthesize_patterns(
            pattern_analysis([40, 40.8, 41.6, 42.4, 43.2, 44])
        )
        self.assertTrue(result["observations"])
        self.assertTrue(result["engineering_evidence"])
        self.assertTrue(result["ml_evidence"])
        self.assertTrue(result["fleet_evidence"])
        self.assertTrue(result["historical_evidence"])
        self.assertTrue(result["pattern_evidence"])

    def test_structured_pattern_preserves_window_and_measurements(self):
        analysis = pattern_analysis([40, 40.8, 41.6, 42.4, 43.2, 44])
        result = self.synthesize_patterns(analysis)
        item = next(item for item in result["pattern_evidence"]
                    if item["supporting_data"]["pattern"] == "SUSTAINED_RISE")
        self.assertEqual(item["supporting_data"]["affected_telemetry"], "motor_temperature")
        self.assertEqual(item["supporting_data"]["window"]["observation_count"], 6)
        self.assertEqual(item["supporting_data"]["metrics"]["net_increase"], 4.0)
        self.assertEqual(item["confidence"], None)
        self.assertIn(item["statement"], result["summary"]["what_pattern_was_observed"])


if __name__ == "__main__":
    unittest.main()
