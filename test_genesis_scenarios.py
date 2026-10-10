"""Deterministic operational-scenario validation for the existing Genesis stack."""

import unittest

from baseline_engine import BaselineEngine
from comparison_engine import ComparisonEngine
from decision_pipeline import DecisionPipeline
from demo_genesis_investigation import (
    demo_historical_incidents,
    demo_peer_records,
    demo_telemetry_records,
)
from evidence_engine import EvidenceEngine
from fleet_baseline import FleetBaseline
from genesis import Genesis
from history import History
from incident_manager import IncidentManager
from recommendation_engine import RecommendationEngine
from reliability_memory import ReliabilityMemory
from reliability_state import ReliabilityState
from telemetry_features import TelemetryFeatureBuilder


def healthy_telemetry(count=8):
    """A low-temperature ABB/AMR path using the shared deterministic demo schema."""
    records = demo_telemetry_records(count=count)
    temperatures = (41.0, 41.5, 42.0, 41.8, 42.2, 42.4, 42.1, 42.3)
    for index, record in enumerate(records):
        record.update({
            "motor_temperature": temperatures[index],
            "ambient_temperature": 25.0,
            "battery_level": 80.0 - 0.5 * index,
            "workload": 30.0 + 2.0 * index,
        })
    return records


def battery_telemetry():
    records = healthy_telemetry(count=6)
    for record, level in zip(records, (82.0, 77.0, 70.0, 63.0, 55.0, 4.0)):
        record["battery_level"] = level
    return records


class DeterministicZeroRiskTestModel:
    """A test double, never used as a Genesis production/model artifact."""

    def predict(self, _feature_record):
        return {"probability": 0.05, "prediction": 0}


def build_test_pipeline(prediction_engine=None):
    history = History()
    return DecisionPipeline(
        prediction_engine=prediction_engine,
        diagnosis_engine=None,
        recommendation_engine=RecommendationEngine(),
        reliability_state=ReliabilityState(),
        incident_manager=IncidentManager(history),
        evidence_engine=EvidenceEngine(),
        comparison_engine=ComparisonEngine(history_window=10),
        baseline_engine=BaselineEngine(minimum_records=10),
    )


def run_test_pipeline(raw_records, prediction_engine=None, fail_at=None, recover_at=None):
    builder = TelemetryFeatureBuilder()
    pipeline = build_test_pipeline(prediction_engine)
    feature_history = []
    results = []
    previous_state = None
    for step, raw in enumerate(raw_records, start=1):
        feature = builder.build({
            "identity": {
                "robot_id": raw["robot_id"],
                "manufacturer": raw.get("manufacturer"),
                "robot_type": raw.get("robot_type"),
            },
            "telemetry": {
                key: value for key, value in raw.items()
                if key not in {"robot_id", "manufacturer", "robot_type"}
            },
        })
        if step == fail_at:
            feature["failure_event"] = True
            feature["failure_type"] = "thermal"
        if step == recover_at:
            feature["recovery_event"] = True
        result = pipeline.evaluate(
            feature,
            previous_state=previous_state,
            historical_records=feature_history,
        )
        results.append(result)
        if step == fail_at:
            incident = pipeline.incident_manager.get_active_incident(raw["robot_id"])
            incident.add_action("Test fixture recorded a recovery action.")
        feature_history.append(feature)
        previous_state = result["state"]
    return results, pipeline


def peer_record(robot_id, temperature, time_step, manufacturer="ABB", robot_type="AMR"):
    return {
        "robot_id": robot_id,
        "manufacturer": manufacturer,
        "robot_type": robot_type,
        "time_step": time_step,
        "motor_temperature": float(temperature),
        "ambient_temperature": 22.0,
        "thermal_rise": float(temperature) - 22.0,
        "battery_level": 80.0,
        "battery_voltage": 48.0,
        "battery_current": 12.0,
        "battery_temperature": 30.0,
        "power_consumption": 800.0,
        "voltage_drop": 0.5,
        "workload": 45.0,
    }


class GenesisScenarioValidationTests(unittest.TestCase):
    def test_01_healthy_robot_with_test_model_can_reach_healthy_without_incident(self):
        results, _ = run_test_pipeline(
            healthy_telemetry(), DeterministicZeroRiskTestModel(),
        )
        result = results[-1]
        self.assertEqual(result["observation_quality"]["status"], "AVAILABLE")
        self.assertEqual(result["risk"]["engineering"]["signals"], [])
        self.assertEqual(result["risk"]["probability"], 0.05)  # test-double output only
        self.assertEqual(result["state"], ReliabilityState.HEALTHY)
        self.assertIsNone(result["incident"])

    def test_02_no_model_on_healthy_public_api_does_not_fabricate_health_or_ml(self):
        result = Genesis().investigate(healthy_telemetry())
        self.assertEqual(result["observation_quality"]["status"], "AVAILABLE")
        self.assertEqual(result["engineering_signals"]["signals"], [])
        self.assertIsNone(result["ml_inference"]["probability"])
        self.assertFalse(result["ml_inference"]["prediction_available"])
        self.assertEqual(result["reliability_state"]["current"], ReliabilityState.WATCH)

    def test_03_degraded_telemetry_stays_watch_and_requests_evidence_verification(self):
        records = healthy_telemetry(count=6)
        records[-1]["battery_voltage"] = None
        result = Genesis().investigate(records)
        self.assertNotEqual(result["observation_quality"]["status"], "AVAILABLE")
        self.assertIn(
            result["observation_quality"]["groups"]["battery"]["status"],
            ("DEGRADED", "INSUFFICIENT"),
        )
        self.assertEqual(result["reliability_state"]["current"], ReliabilityState.WATCH)
        self.assertIsNone(result["ml_inference"]["probability"])
        self.assertIsNone(result["ml_inference"]["diagnosis"])
        self.assertIn("verify", result["recommendation"]["recommendation"].lower())

    def test_04_critical_motor_temperature_uses_existing_signal_and_opens_incident(self):
        result = Genesis().investigate(demo_telemetry_records(count=6))
        signals = {item["signal"] for item in result["engineering_signals"]["signals"]}
        self.assertIn("critical_motor_temperature", signals)
        self.assertIn("critical_thermal_rise", signals)
        self.assertEqual(result["reliability_state"]["current"], ReliabilityState.CRITICAL)
        self.assertEqual(result["incident"]["status"], "ACTIVE")
        self.assertTrue(result["recommendation"]["recommendation"])
        self.assertIsNone(result["ml_inference"]["diagnosis"])

    def test_05_battery_problem_stays_battery_evidence_without_thermal_cause(self):
        result = Genesis().investigate(battery_telemetry())
        signals = {item["signal"] for item in result["engineering_signals"]["signals"]}
        self.assertIn("critical_battery_level", signals)
        self.assertNotIn("critical_motor_temperature", signals)
        self.assertNotIn("critical_thermal_rise", signals)
        self.assertEqual(result["reliability_state"]["current"], ReliabilityState.CRITICAL)
        self.assertIsNone(result["ml_inference"]["diagnosis"])
        battery_observations = [
            item for item in result["observations"] if item.get("field") == "battery_level"
        ]
        self.assertTrue(battery_observations)
        self.assertEqual(battery_observations[-1]["value"], 4.0)

    def test_06_fleet_wide_increase_is_reported_as_peer_wide_context(self):
        baseline = FleetBaseline()
        previous = [peer_record("R001", 42, 1), peer_record("R002", 43, 1), peer_record("R003", 44, 1)]
        current = [peer_record("R001", 62, 2), peer_record("R002", 63, 2), peer_record("R003", 64, 2)]
        subject = peer_record("R004", 63, 2)
        result = baseline.compare(
            subject,
            peer_records=current,
            previous_peer_records=previous,
        )
        metric = result["metrics"]["motor_temperature"]
        self.assertEqual(metric["status"], "NORMAL")
        self.assertEqual(metric["pattern"], "peer_wide")
        self.assertEqual(result["fleet_pattern"], "peer_wide")

    def test_07_robot_specific_outlier_uses_only_comparable_peers(self):
        records = demo_telemetry_records(count=6)
        peers = demo_peer_records()
        peers.append(peer_record("R004", 61, 6))  # current robot must be excluded
        result = Genesis(peer_records=peers).investigate(records)
        metric = result["fleet_context"]["metrics"]["motor_temperature"]
        self.assertEqual(metric["status"], "OUTLIER")
        self.assertEqual(metric["peer_count"], 3)
        self.assertEqual(metric["peer_mean"], 43.0)
        self.assertEqual(metric["peer_minimum"], 42.0)
        self.assertEqual(metric["peer_maximum"], 44.0)
        self.assertNotIn("R005", [peer.get("robot_id") for peer in result["fleet_context"].get("peer_records", [])])

    def test_08_current_robot_and_other_robot_types_are_excluded_by_baseline(self):
        baseline = FleetBaseline()
        subject = peer_record("R004", 61, 6)
        peers = [
            peer_record("R001", 42, 6),
            peer_record("R002", 43, 6),
            peer_record("R003", 44, 6),
            peer_record("R004", 61, 6),
            peer_record("R005", 70, 6, manufacturer="KUKA", robot_type="robotic_arm"),
        ]
        result = baseline.compare(subject, peer_records=peers)
        self.assertEqual(result["comparable_robot_count"], 3)
        self.assertEqual(result["metrics"]["motor_temperature"]["peer_mean"], 43.0)

    def test_09_fleet_context_does_not_change_risk_state_or_incident(self):
        records = demo_telemetry_records(count=6)
        outlier_result = Genesis(peer_records=demo_peer_records()).investigate(records)
        matched_peers = [peer_record(f"P{i}", 59 + i, 6) for i in range(3)]
        contextual_result = Genesis(peer_records=matched_peers).investigate(records)
        self.assertNotEqual(
            outlier_result["fleet_context"]["metrics"]["motor_temperature"]["status"],
            contextual_result["fleet_context"]["metrics"]["motor_temperature"]["status"],
        )
        self.assertEqual(outlier_result["reliability_state"], contextual_result["reliability_state"])
        self.assertEqual(outlier_result["engineering_signals"], contextual_result["engineering_signals"])
        self.assertEqual(outlier_result["incident"]["status"], contextual_result["incident"]["status"])

    def test_10_failure_recovery_closes_only_after_existing_recovery_conditions(self):
        records, pipeline = run_test_pipeline(
            healthy_telemetry(),
            DeterministicZeroRiskTestModel(),
            fail_at=6,
            recover_at=7,
        )
        failed, recovering, recovered = records[5], records[6], records[7]
        self.assertEqual(failed["state"], ReliabilityState.FAILED)
        self.assertEqual(failed["incident"]["status"], "FAILED")
        self.assertEqual(recovering["state"], ReliabilityState.RECOVERING)
        self.assertEqual(recovering["incident"]["status"], "RECOVERING")
        self.assertEqual(recovered["state"], ReliabilityState.HEALTHY)
        self.assertEqual(recovered["incident"]["status"], "CLOSED")
        self.assertEqual(recovered["incident"]["outcome"]["final_state"], "HEALTHY")
        self.assertIsNone(recovered["diagnosis"])
        events = recovered["incident"]["evidence"]
        self.assertTrue(any(event.get("event_type") == "failure" for event in events))
        self.assertTrue(any(event.get("event_type") == "recovery" for event in events))
        self.assertEqual(
            recovered["incident"]["actions"],
            ["Test fixture recorded a recovery action."],
        )
        incident = pipeline.incident_manager.history.incidents[0]
        self.assertEqual(incident.status, "CLOSED")

    def test_11_reliability_memory_excludes_current_incident_from_matches(self):
        result = Genesis(historical_incidents=demo_historical_incidents()).investigate(
            demo_telemetry_records(count=6)
        )
        current_id = result["incident"]["incident_id"]
        matched_ids = {item["incident_id"] for item in result["historical_memory"]["incidents"]}
        self.assertNotIn(current_id, matched_ids)
        self.assertEqual(matched_ids, {"HIST-INC-001", "HIST-INC-002"})

    def test_12_memory_match_reasons_are_explicit_and_not_causal(self):
        result = Genesis(historical_incidents=demo_historical_incidents()).investigate(
            demo_telemetry_records(count=6)
        )
        allowed = {
            "same_robot", "same_manufacturer", "same_robot_type",
            "same_engineering_signal", "same_diagnosis",
            "same_reliability_state", "same_incident_category",
        }
        for incident in result["historical_memory"]["incidents"]:
            self.assertTrue(set(incident["similarity_reasons"]).issubset(allowed))
        statements = [item["statement"].lower() for item in result["evidence_synthesis"]["historical_evidence"]]
        self.assertTrue(any("matched on" in statement for statement in statements))
        self.assertFalse(any("caused" in statement for statement in statements))

    def test_13_missing_model_and_diagnosis_never_get_synthetic_outputs(self):
        result = Genesis().investigate(demo_telemetry_records(count=6))
        self.assertIsNone(result["ml_inference"]["probability"])
        self.assertFalse(result["ml_inference"]["prediction_available"])
        self.assertIsNone(result["ml_inference"]["diagnosis"])

    def test_14_unavailable_model_watch_does_not_open_an_incident_by_itself(self):
        result = Genesis().investigate(healthy_telemetry())
        self.assertEqual(result["reliability_state"]["current"], ReliabilityState.WATCH)
        self.assertEqual(result["engineering_signals"]["signals"], [])
        self.assertIsNone(result["incident"])


if __name__ == "__main__":
    unittest.main()
