import unittest

from incident_explanation import (
    ENGINEERING_SIGNAL, HISTORICAL_COMPARISON, ML_INFERENCE,
    OBSERVATION, IncidentExplanation,
)


def make_context(**updates):
    features = {
        "robot_id": "SIM-047", "site_id": "SITE-1", "time_step": 12,
        "motor_temperature": 58.0, "ambient_temperature": 25.0,
        "thermal_rise": 33.0, "temperature_change": 2.0,
        "temperature_rate_3": 4.0, "battery_level": 42.0,
        "battery_voltage": 44.1, "battery_current": 32.0,
        "battery_temperature": 37.0, "voltage_drop": 1.2,
        "battery_change": -2.0, "battery_voltage_decline_3": 0.8,
        "battery_current_change": 3.0, "battery_temperature_change": 1.0,
        "workload": 65.0, "power_consumption": 1200.0,
        "power_rate_3": 45.0, "robot_state": "working",
        "thermal_elevated_persistence": 3,
    }
    quality = {
        "status": "AVAILABLE", "prediction_ready": True,
        "any_major_group_limited": False,
        "history": {"available_prior_observations": 5, "required_prior_observations": 4},
        "groups": {
            group: {"status": "AVAILABLE", "issues": []}
            for group in ("thermal", "battery", "workload")
        },
    }
    result = {
        "robot_id": "SIM-047", "time_step": 12, "state": "WARNING",
        "previous_state": "WATCH", "state_transition": {"from": "WATCH", "to": "WARNING", "changed": True},
        "risk": {
            "probability": 0.78, "prediction": 1, "model_prediction": 1,
            "prediction_available": True, "fused_risk": "WARNING",
            "engineering": {"severity": "warning", "status": "warning", "signals": [
                {"signal": "voltage_drop", "severity": "warning", "value": 1.2}
            ]},
        },
        "observation_quality": quality,
        "diagnosis": {"failure_type": "battery", "probable_cause": "possible battery degradation", "confidence": 0.81},
        "recommendation": {"recommendation": "Inspect battery and power system.", "probable_cause": "possible battery degradation", "risk_level": "HIGH"},
        "comparison": {"status": "comparison_available", "metrics": {"voltage_delta": -0.8}},
        "baseline": {"status": "baseline_available", "metrics": {"average_battery_level": 70.0}},
        "timeline": {"events": []}, "incident": None,
    }
    for key, value in updates.items():
        if key == "features":
            features.update(value)
        elif key == "quality":
            result["observation_quality"] = value
        else:
            result[key] = value
    return result, features


def build(**updates):
    result, features = make_context(**updates)
    return IncidentExplanation.build(result, features)


class IncidentExplanationTests(unittest.TestCase):
    def test_battery_incident(self):
        report = build()
        self.assertIn("battery_level", [item["field"] for item in report["evidence_summary"]["battery"]])
        self.assertEqual(report["identity"]["robot_id"], "SIM-047")

    def test_thermal_incident(self):
        report = build()
        self.assertIn("motor_temperature", [item["field"] for item in report["evidence_summary"]["thermal"]])

    def test_healthy_without_incident(self):
        result, features = make_context(state="HEALTHY", incident=None)
        result["incident"] = None
        report = IncidentExplanation.build(result, features)
        self.assertEqual(report["identity"]["status"], "NO_INCIDENT")
        self.assertIsNone(report["identity"]["incident_id"])

    def test_degraded_quality_reasons_are_reused(self):
        result, features = make_context()
        result["observation_quality"]["status"] = "DEGRADED"
        result["observation_quality"]["groups"]["battery"] = {
            "status": "DEGRADED", "issues": [{"check": "missing_values", "fields": ["battery_voltage"]}],
        }
        report = IncidentExplanation.build(result, features)
        self.assertEqual(report["observation_quality"]["battery"], "DEGRADED")
        self.assertTrue(any(reason["group"] == "battery" for reason in report["observation_quality"]["reasons"]))

    def test_prediction_unavailable(self):
        result, features = make_context()
        result["risk"].update(prediction_available=False, probability=None, prediction=None, unavailable_reason="warm-up")
        report = IncidentExplanation.build(result, features)
        self.assertFalse(report["ml_inference"]["prediction_available"])
        self.assertIn("warm-up", report["limitations"])

    def test_history_unavailable_is_explicit(self):
        result, features = make_context(comparison={"status": "insufficient_data", "metrics": {}}, baseline={"status": "insufficient_data", "metrics": {}})
        report = IncidentExplanation.build(result, features)
        self.assertEqual(report["historical_evidence"]["status"], "UNAVAILABLE")
        self.assertEqual(report["historical_evidence"]["message"], "historical comparison unavailable")

    def test_diagnosis_unavailable(self):
        result, features = make_context(diagnosis=None)
        report = IncidentExplanation.build(result, features)
        self.assertIsNone(report["ml_inference"]["diagnosis"])
        self.assertIn("Diagnosis unavailable", report["limitations"])

    def test_recommendation_present(self):
        self.assertEqual(build()["recommendation"]["status"], "AVAILABLE")

    def test_recommendation_absent(self):
        result, features = make_context(recommendation=None)
        self.assertEqual(IncidentExplanation.build(result, features)["recommendation"]["status"], "UNAVAILABLE")

    def test_human_action_pending(self):
        self.assertEqual(build()["human_action"]["status"], "PENDING")

    def test_outcome_pending(self):
        self.assertEqual(build()["outcome"]["status"], "OUTCOME_PENDING")

    def test_resolved_incident_exposes_outcome(self):
        incident = {"incident_id": "INC001", "robot_id": "SIM-047", "status": "CLOSED", "outcome": {"resolved": True}, "actions": []}
        result, features = make_context(incident=incident)
        report = IncidentExplanation.build(result, features)
        self.assertEqual(report["outcome"]["status"], "RESOLVED")
        self.assertEqual(report["outcome"]["details"], {"resolved": True})

    def test_observation_and_inference_types_are_distinct(self):
        report = build()
        self.assertEqual(report["observations"][0]["type"], OBSERVATION)
        self.assertTrue(all(item["type"] == ML_INFERENCE for item in report["evidence_summary"]["ml_inference"]))
        self.assertTrue(all(item["type"] == ENGINEERING_SIGNAL for item in report["engineering_signals"]["items"]))
        self.assertTrue(all(item["type"] == HISTORICAL_COMPARISON for item in report["evidence_summary"]["fleet_history"]))
        self.assertFalse(report["ml_inference"]["diagnosis"]["confirmed"])

    def test_no_missing_telemetry_values_are_invented(self):
        result, features = make_context(features={"battery_voltage": None, "ambient_temperature": None})
        report = IncidentExplanation.build(result, features)
        fields = [item["field"] for item in report["observations"]]
        self.assertNotIn("battery_voltage", fields)
        self.assertNotIn("ambient_temperature", fields)

    def test_evidence_groups_have_no_duplicate_entries(self):
        report = build()
        for items in report["evidence_summary"].values():
            keys = [repr(item) for item in items]
            self.assertEqual(len(keys), len(set(keys)))

    def test_report_schema_handles_all_lifecycle_states(self):
        for status in ("OPEN", "ACTIVE", "FAILED", "RECOVERING", "CLOSED"):
            with self.subTest(status=status):
                incident = {"incident_id": "INC001", "robot_id": "SIM-047", "status": status,
                            "outcome": {"resolved": True} if status == "CLOSED" else None,
                            "actions": []}
                result, features = make_context(incident=incident)
                report = IncidentExplanation.build(result, features)
                self.assertEqual(report["identity"]["status"], status)
                self.assertIn("observations", report)
                self.assertIn("evidence_summary", report)
                self.assertIn("outcome", report)


if __name__ == "__main__":
    unittest.main()
