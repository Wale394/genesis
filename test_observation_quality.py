import unittest

from evidence_engine import EvidenceEngine
from decision_pipeline import DecisionPipeline
from feature_contract import DEPLOYABLE_FEATURES
from history import History
from incident_manager import IncidentManager
from reliability_fusion import ReliabilityFusion
from reliability_state import ReliabilityState
from telemetry_features import TelemetryFeatureBuilder
from recommendation_engine import RecommendationEngine


def sample_stream(count=6, static_temperature=False):
    builder = TelemetryFeatureBuilder()
    records = []
    for step in range(count):
        motor = 40.0 if static_temperature else 40.0 + 0.4 * step
        snapshot = {
            "identity": {
                "robot_id": "Q-1",
                "manufacturer": "Maker",
                "robot_type": "AMR",
            },
            "telemetry": {
                "time_step": step,
                "motor_temperature": motor,
                "ambient_temperature": 25.0 + 0.1 * step,
                "battery_level": 80.0 - 0.8 * step,
                "battery_voltage": 48.0 - 0.02 * step,
                "battery_current": 20.0 + 0.1 * step,
                "battery_temperature": 30.0 + 0.1 * step,
                "power_consumption": 800.0 + 10.0 * step,
                "voltage_drop": 0.0,
                "workload": 40.0 + 5.0 * step,
                "robot_state": "working",
            },
        }
        records.append(builder.build(snapshot))
    return records


class ObservationQualityTests(unittest.TestCase):
    def setUp(self):
        self.records = sample_stream()
        self.current = self.records[-1]
        self.history = self.records[:-1]

    def test_missing_telemetry_marks_battery_insufficient(self):
        record = dict(self.current)
        record["battery_voltage"] = None
        from observation_quality import ObservationQuality, INSUFFICIENT
        quality = ObservationQuality().assess(record, self.history)
        self.assertEqual(quality["groups"]["battery"]["status"], INSUFFICIENT)
        self.assertIn("battery_voltage", quality["groups"]["battery"]["missing_fields"])

    def test_insufficient_history_blocks_prediction(self):
        from observation_quality import ObservationQuality, INSUFFICIENT
        record = sample_stream(count=1)[0]
        quality = ObservationQuality().assess(record, [])
        self.assertFalse(quality["prediction_ready"])
        self.assertEqual(quality["groups"]["thermal"]["status"], INSUFFICIENT)

    def test_invalid_values_degrade_battery_evidence(self):
        from observation_quality import ObservationQuality, DEGRADED
        record = dict(self.current)
        record["battery_level"] = 120.0
        quality = ObservationQuality().assess(record, self.history)
        self.assertEqual(quality["groups"]["battery"]["status"], DEGRADED)
        self.assertTrue(any(
            issue["check"] == "invalid_values"
            for issue in quality["groups"]["battery"]["issues"]
        ))

    def test_static_sensor_is_flagged_when_related_workload_varies(self):
        from observation_quality import ObservationQuality, DEGRADED
        records = sample_stream(static_temperature=True)
        quality = ObservationQuality().assess(records[-1], records[:-1])
        self.assertEqual(quality["groups"]["thermal"]["status"], DEGRADED)
        self.assertTrue(any(
            issue["check"] == "unexpected_static_sensor"
            for issue in quality["groups"]["thermal"]["issues"]
        ))

    def test_abrupt_implausible_change_is_flagged(self):
        from observation_quality import ObservationQuality, DEGRADED
        record = dict(self.current)
        record["motor_temperature"] = 90.0
        record["thermal_rise"] = round(90.0 - record["ambient_temperature"], 2)
        quality = ObservationQuality().assess(record, self.history)
        self.assertEqual(quality["groups"]["thermal"]["status"], DEGRADED)
        self.assertTrue(any(
            issue["check"] == "abrupt_change"
            for issue in quality["groups"]["thermal"]["issues"]
        ))

    def test_related_thermal_measurements_must_agree(self):
        from observation_quality import ObservationQuality, DEGRADED
        record = dict(self.current)
        record["thermal_rise"] += 5.0
        quality = ObservationQuality().assess(record, self.history)
        self.assertEqual(quality["groups"]["thermal"]["status"], DEGRADED)

    def test_normal_telemetry_is_available(self):
        from observation_quality import ObservationQuality, AVAILABLE
        quality = ObservationQuality().assess(self.current, self.history)
        self.assertTrue(quality["prediction_ready"])
        self.assertEqual(quality["status"], AVAILABLE)
        self.assertTrue(all(group["status"] == AVAILABLE for group in quality["groups"].values()))

    def test_evidence_transparency_records_probability_and_group_quality(self):
        from observation_quality import ObservationQuality
        quality = ObservationQuality().assess(self.current, self.history)
        evidence = EvidenceEngine().build_evidence_summary(
            self.current,
            risk_result={"probability": 0.23, "prediction": 0, "prediction_available": True},
            observation_quality=quality,
        )
        transparency = evidence["inference_transparency"]
        self.assertEqual(transparency["prediction_probability"], 0.23)
        self.assertEqual(transparency["predicted_risk"], "no_failure")
        self.assertEqual(transparency["thermal_evidence_quality"], "AVAILABLE")
        self.assertFalse(transparency["major_signal_group_limited"])

    def test_limited_evidence_is_not_reported_as_healthy(self):
        state = ReliabilityState()
        available = {"status": "AVAILABLE"}
        degraded = {"status": "DEGRADED"}
        self.assertEqual(
            state.determine_state(0.02, 0, observation_quality=available),
            state.HEALTHY,
        )
        self.assertEqual(
            state.determine_state(0.02, 0, observation_quality=degraded),
            state.WATCH,
        )
        fusion = ReliabilityFusion().evaluate(
            self.current, 0.02, 0, observation_quality=degraded
        )
        self.assertEqual(fusion["final"]["risk"], "WATCH")
        self.assertTrue(fusion["final"]["confidence_limited"])

    def test_quality_contract_does_not_change_risk_model_feature_schema(self):
        self.assertIn("motor_temperature", DEPLOYABLE_FEATURES)
        self.assertNotIn("observation_quality", DEPLOYABLE_FEATURES)

    @staticmethod
    def _pipeline(prediction_engine):
        class Diagnosis:
            def diagnose(self, record):
                raise AssertionError("Diagnosis should not run for a no-failure prediction")

        class Comparison:
            def compare_to_history(self, record, history):
                return {}

        class Baseline:
            def build_baseline(self, history):
                return {}

        return DecisionPipeline(
            prediction_engine,
            Diagnosis(),
            RecommendationEngine(),
            ReliabilityState(),
            IncidentManager(History()),
            EvidenceEngine(),
            Comparison(),
            Baseline(),
        )

    def test_pipeline_skips_prediction_during_warmup_and_explains_limited_evidence(self):
        class Prediction:
            def predict(self, record):
                raise AssertionError("Prediction must wait for the shared warm-up contract")

        record = sample_stream(count=1)[0]
        result = self._pipeline(Prediction()).evaluate(record)
        self.assertIsNone(result["risk"]["probability"])
        self.assertEqual(result["state"], ReliabilityState.WATCH)
        self.assertIn("before treating a low risk score", result["recommendation"]["recommendation"])

    def test_pipeline_records_quality_with_an_actual_risk_prediction(self):
        class Prediction:
            def predict(self, record):
                return {"probability": 0.23, "prediction": 0}

        result = self._pipeline(Prediction()).evaluate(
            self.current,
            historical_records=self.history,
        )
        transparency = result["evidence"]["inference_transparency"]
        self.assertEqual(transparency["prediction_probability"], 0.23)
        self.assertEqual(transparency["predicted_risk"], "HEALTHY")
        self.assertEqual(result["observation_quality"]["status"], "AVAILABLE")
        self.assertTrue(any(
            event["event_type"] == "observation_quality"
            for event in result["timeline"]["events"]
        ))

    def test_pipeline_does_not_call_degraded_low_risk_healthy(self):
        class Prediction:
            def predict(self, record):
                return {"probability": 0.02, "prediction": 0}

        record = dict(self.current)
        record["battery_level"] = 120.0
        result = self._pipeline(Prediction()).evaluate(
            record,
            historical_records=self.history,
        )
        self.assertEqual(result["risk"]["prediction"], 0)
        self.assertEqual(result["state"], ReliabilityState.WATCH)
        self.assertIn("battery", result["recommendation"]["recommendation"])


if __name__ == "__main__":
    unittest.main()
