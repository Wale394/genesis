import unittest

from decision_pipeline import DecisionPipeline
from evidence_engine import EvidenceEngine
from history import History
from incident_manager import IncidentManager
from recommendation_engine import RecommendationEngine
from reliability_state import ReliabilityState
from telemetry_features import TelemetryFeatureBuilder


def telemetry_sequence(count=9):
    builder = TelemetryFeatureBuilder()
    records = []
    for step in range(count):
        records.append(builder.build({
            "identity": {
                "robot_id": "PIPE-1",
                "manufacturer": "Maker",
                "robot_type": "AMR",
            },
            "telemetry": {
                "time_step": step,
                "motor_temperature": 40.0 + 0.4 * step,
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
        }))
    return records


class FakePredictionEngine:
    def __init__(self, probability=0.05, prediction=0):
        self.probability = probability
        self.prediction = prediction
        self.calls = 0

    def predict(self, record):
        self.calls += 1
        return {"probability": self.probability, "prediction": self.prediction}


class FakeDiagnosisEngine:
    def __init__(self):
        self.calls = 0

    def diagnose(self, record):
        self.calls += 1
        return {
            "failure_type": "thermal",
            "probable_cause": "thermal pattern",
            "confidence": 0.8,
        }


class CountingRecommendationEngine(RecommendationEngine):
    def __init__(self):
        self.calls = 0

    def recommend(self, *args, **kwargs):
        self.calls += 1
        return super().recommend(*args, **kwargs)


class CountingIncidentManager(IncidentManager):
    def __init__(self, history):
        super().__init__(history)
        self.close_calls = 0

    def close_incident(self, *args, **kwargs):
        self.close_calls += 1
        return super().close_incident(*args, **kwargs)


class DecisionPipelineTests(unittest.TestCase):
    def setUp(self):
        self.records = telemetry_sequence()

    def make_pipeline(self, probability=0.05, prediction=0):
        self.history_store = History()
        self.incident_manager = CountingIncidentManager(self.history_store)
        self.predictor = FakePredictionEngine(probability, prediction)
        self.diagnosis = FakeDiagnosisEngine()
        self.recommendations = CountingRecommendationEngine()
        self.pipeline = DecisionPipeline(
            self.predictor,
            self.diagnosis,
            self.recommendations,
            ReliabilityState(),
            self.incident_manager,
            EvidenceEngine(),
            type("Comparison", (), {"compare_to_history": lambda self, r, h: {}})(),
            type("Baseline", (), {"build_baseline": lambda self, h: {}})(),
        )
        return self.pipeline

    def evaluate_at(self, pipeline, index, previous_state=None, **overrides):
        record = dict(self.records[index])
        record.update(overrides)
        return pipeline.evaluate(
            record,
            previous_state=previous_state,
            historical_records=self.records[:index],
        )

    def test_normal_healthy_robot_with_sufficient_evidence(self):
        pipeline = self.make_pipeline()
        result = self.evaluate_at(pipeline, 5)
        self.assertEqual(result["state"], ReliabilityState.HEALTHY)
        self.assertIsNone(result["incident"])
        self.assertEqual(result["explanation"]["identity"]["status"], "NO_INCIDENT")

    def test_low_risk_with_degraded_telemetry_stays_conservative(self):
        pipeline = self.make_pipeline(0.02, 0)
        result = self.evaluate_at(pipeline, 5, battery_level=120.0)
        self.assertEqual(result["state"], ReliabilityState.WATCH)
        self.assertIn("battery", result["recommendation"]["recommendation"])

    def test_critical_engineering_signal_overrides_ml_through_fusion(self):
        pipeline = self.make_pipeline(0.18, 0)
        result = self.evaluate_at(pipeline, 5, battery_level=5.0)
        self.assertEqual(result["risk"]["model_prediction"], 0)
        self.assertEqual(result["risk"]["prediction"], 1)
        self.assertEqual(result["risk"]["engineering"]["severity"], "critical")
        self.assertEqual(result["state"], ReliabilityState.CRITICAL)

    def test_ml_high_risk_prediction_produces_warning_state(self):
        pipeline = self.make_pipeline(0.75, 1)
        result = self.evaluate_at(pipeline, 5)
        self.assertEqual(result["risk"]["fused_risk"], "WARNING")
        self.assertEqual(result["state"], ReliabilityState.WARNING)
        self.assertEqual(pipeline.diagnosis_engine.calls, 1)

    def test_warmup_prediction_is_unavailable_and_not_healthy(self):
        pipeline = self.make_pipeline()
        result = self.evaluate_at(pipeline, 0)
        self.assertEqual(pipeline.prediction_engine.calls, 0)
        self.assertIsNone(result["risk"]["probability"])
        self.assertEqual(result["state"], ReliabilityState.WATCH)
        self.assertIsNone(result["incident"])

    def test_incident_opens_when_reliability_becomes_abnormal(self):
        pipeline = self.make_pipeline(0.75, 1)
        result = self.evaluate_at(pipeline, 5)
        self.assertEqual(len(self.history_store.incidents), 1)
        self.assertEqual(result["incident"]["status"], "ACTIVE")
        self.assertEqual(result["explanation"]["identity"]["status"], "ACTIVE")
        self.assertEqual(len(pipeline.reliability_memory.entries), 1)
        self.assertEqual(
            pipeline.reliability_memory.get_by_incident_id(result["incident"]["incident_id"])["lifecycle"]["status"],
            "ACTIVE",
        )

    def test_incident_recovers_closes_once_and_preserves_outcome(self):
        pipeline = self.make_pipeline(0.95, 1)
        first = self.evaluate_at(pipeline, 5)
        incident = self.history_store.incidents[0]
        incident.add_action({"action": "maintenance completed"})
        self.assertEqual(first["incident"]["status"], "ACTIVE")

        failed = self.evaluate_at(
            pipeline, 6, previous_state=first["state"],
            failure_event=True, failure_type="thermal",
        )
        self.assertEqual(failed["state"], ReliabilityState.FAILED)
        self.assertEqual(failed["incident"]["status"], "FAILED")
        self.assertEqual(failed["explanation"]["identity"]["status"], "FAILED")

        pipeline.prediction_engine.probability = 0.05
        pipeline.prediction_engine.prediction = 0
        recovering = self.evaluate_at(
            pipeline, 7, previous_state=failed["state"], recovery_event=True,
        )
        self.assertEqual(recovering["state"], ReliabilityState.RECOVERING)
        self.assertEqual(recovering["explanation"]["identity"]["status"], "RECOVERING")
        self.assertEqual(
            sum(e["event_type"] == "recovery" for e in recovering["timeline"]["events"]),
            1,
        )

        healthy = self.evaluate_at(
            pipeline, 8, previous_state=recovering["state"],
        )
        closed = healthy["incident"]
        self.assertEqual(healthy["state"], ReliabilityState.HEALTHY)
        self.assertEqual(closed["status"], "CLOSED")
        self.assertEqual(healthy["explanation"]["identity"]["status"], "CLOSED")
        self.assertEqual(healthy["explanation"]["outcome"]["status"], "RESOLVED")
        self.assertEqual(len(pipeline.reliability_memory.entries), 1)
        self.assertEqual(
            pipeline.reliability_memory.get_by_incident_id(closed["incident_id"])["lifecycle"]["status"],
            "CLOSED",
        )
        self.assertEqual(closed["end_time_step"], 8)
        self.assertEqual(self.incident_manager.close_calls, 1)
        self.assertEqual(closed["outcome"]["failure_type"], "thermal")
        self.assertEqual(closed["outcome"]["final_state"], "HEALTHY")
        self.assertEqual(closed["actions"], [{"action": "maintenance completed"}])
        self.assertEqual(
            sum(e.get("event_type") == "recovery" for e in closed["evidence"]),
            1,
        )

    def test_recommendation_once_and_timeline_has_one_of_each_decision_event(self):
        pipeline = self.make_pipeline(0.75, 1)
        result = self.evaluate_at(pipeline, 5)
        events = result["timeline"]["events"]
        for event_type in (
            "prediction", "reliability_inference", "observation_quality",
            "diagnosis", "state_change", "recommendation",
        ):
            self.assertEqual(sum(e["event_type"] == event_type for e in events), 1, event_type)
        positions = {event["event_type"]: index for index, event in enumerate(events)}
        self.assertLess(positions["observation"], positions["observation_quality"])
        self.assertLess(positions["observation_quality"], positions["prediction"])
        self.assertLess(positions["prediction"], positions["reliability_inference"])
        self.assertLess(positions["reliability_inference"], positions["diagnosis"])
        self.assertLess(positions["diagnosis"], positions["recommendation"])
        self.assertEqual(pipeline.recommendation_engine.calls, 1)

    def test_incident_manager_open_transitions_to_active(self):
        manager = IncidentManager(History())
        incident = manager.create_incident("R1", 3)
        self.assertEqual(incident.status, "OPEN")
        updated = manager.update_incident("R1", 3, observation={"x": 1})
        self.assertIs(updated, incident)
        self.assertEqual(incident.status, "ACTIVE")


if __name__ == "__main__":
    unittest.main()
