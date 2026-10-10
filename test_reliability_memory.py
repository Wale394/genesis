import json
import unittest

from incident_manager import IncidentManager
from history import History
from reliability_memory import ReliabilityMemory
from incident_explanation import IncidentExplanation


def make_incident(incident_id, robot_id, manufacturer="Maker", robot_type="AMR", status="CLOSED", signals=None, diagnosis=None, outcome=None, recommendation="Inspect battery", actions=None):
    return {
        "identity": {
            "incident_id": incident_id, "robot_id": robot_id,
            "manufacturer": manufacturer, "robot_type": robot_type,
            "site_id": "SITE-1", "incident_type": None, "status": status,
            "start_time_step": 5, "end_time_step": 8 if status == "CLOSED" else None,
        },
        "reliability_state": {"current": "HEALTHY" if status == "CLOSED" else "WARNING", "previous": "WARNING"},
        "engineering_signals": {"items": [{"signal": value} for value in (signals or [])]},
        "ml_inference": {
            "prediction_available": True, "probability": 0.78,
            "predicted_risk": "WARNING", "model_prediction": 1,
            "diagnosis": diagnosis,
        },
        "recommendation": {"status": "AVAILABLE" if recommendation else "UNAVAILABLE", "text": recommendation},
        "human_action": {"status": "RECORDED" if actions else "PENDING", "items": actions or []},
        "outcome": {
            "status": "RESOLVED" if outcome else "OUTCOME_PENDING",
            "resolved": bool(outcome), "details": outcome,
        },
        "observations": [{"field": "battery_level", "value": 18.0, "type": "OBSERVATION"}],
        "temporal_evidence": [{"field": "battery_change", "value": -4.0, "type": "OBSERVATION"}],
        "observation_quality": {"overall": "AVAILABLE"},
        "historical_evidence": {"status": "UNAVAILABLE"},
        "limitations": ["Diagnosis unavailable"] if diagnosis is None else [],
    }


def store(memory, report):
    return memory.store_incident(report)


class ReliabilityMemoryTests(unittest.TestCase):
    def setUp(self):
        self.memory = ReliabilityMemory()

    def test_store_incident(self):
        entry = store(self.memory, make_incident("INC001", "R001", signals=["critical_battery_level"]))
        self.assertEqual(entry["identity"]["robot_id"], "R001")
        self.assertEqual(len(self.memory.entries), 1)

    def test_retrieve_by_incident_id(self):
        store(self.memory, make_incident("INC001", "R001"))
        self.assertEqual(self.memory.get_by_id("INC001")["identity"]["incident_id"], "INC001")

    def test_retrieve_by_robot_id(self):
        store(self.memory, make_incident("INC001", "R001"))
        self.assertEqual(len(self.memory.by_robot_id("R001")), 1)

    def test_retrieve_by_manufacturer(self):
        store(self.memory, make_incident("INC001", "R001", manufacturer="Acme"))
        self.assertEqual(len(self.memory.by_manufacturer("Acme")), 1)

    def test_retrieve_by_robot_type(self):
        store(self.memory, make_incident("INC001", "R001", robot_type="Humanoid"))
        self.assertEqual(len(self.memory.by_robot_type("Humanoid")), 1)

    def test_retrieve_by_engineering_signal(self):
        store(self.memory, make_incident("INC001", "R001", signals=["critical_battery_level"]))
        self.assertEqual(len(self.memory.by_engineering_signal("critical_battery_level")), 1)

    def test_retrieve_by_diagnosis(self):
        diagnosis = {"possible_failure_type": "battery", "probable_cause": "possible battery issue", "confidence": 0.8, "confirmed": False}
        store(self.memory, make_incident("INC001", "R001", diagnosis=diagnosis))
        self.assertEqual(len(self.memory.by_diagnosis("battery")), 1)

    def test_similarity_explains_matching_dimensions(self):
        store(self.memory, make_incident("INC001", "R001", signals=["critical_battery_level"]))
        current = make_incident("CURRENT", "R002", robot_type="AMR", status="ACTIVE", signals=["critical_battery_level"])
        match = self.memory.find_similar(current)[0]
        self.assertEqual(match["incident_id"], "INC001")
        self.assertEqual(match["similarity_reasons"], ["same_manufacturer", "same_robot_type", "same_engineering_signal"])

    def test_no_similarity_without_shared_evidence(self):
        store(self.memory, make_incident("INC001", "R001", manufacturer="Maker A", robot_type="AMR"))
        current = make_incident("CURRENT", "R002", manufacturer="Maker B", robot_type="UGV", status="ACTIVE")
        current["reliability_state"] = {"current": "CRITICAL", "previous": None}
        current["engineering_signals"] = {"items": []}
        current["ml_inference"]["diagnosis"] = None
        self.assertEqual(self.memory.find_similar(current), [])

    def test_multiple_historical_incidents(self):
        for number in range(3):
            store(self.memory, make_incident(f"INC00{number}", f"R00{number}", signals=["critical_battery_level"]))
        context = self.memory.historical_context(make_incident("CURRENT", "R999", status="ACTIVE", signals=["critical_battery_level"]))
        self.assertEqual(context["match_count"], 3)

    def test_closed_incident_preserves_outcome(self):
        entry = store(self.memory, make_incident("INC001", "R001", outcome={"repair": "battery replaced"}))
        self.assertEqual(entry["characterization"]["outcome"]["details"], {"repair": "battery replaced"})

    def test_pending_outcome_stays_pending(self):
        entry = store(self.memory, make_incident("INC001", "R001", status="ACTIVE", outcome=None))
        self.assertEqual(entry["characterization"]["outcome"]["status"], "pending")
        self.assertIsNone(entry["characterization"]["outcome"]["details"])

    def test_update_existing_incident_replaces_one_record(self):
        store(self.memory, make_incident("INC001", "R001", status="ACTIVE"))
        store(self.memory, make_incident("INC001", "R001", status="CLOSED", outcome={"resolved": True}))
        self.assertEqual(len(self.memory.entries), 1)
        self.assertEqual(self.memory.get_by_id("INC001")["lifecycle"]["status"], "CLOSED")

    def test_human_action_is_preserved(self):
        action = {"action": "battery replaced", "actor": "operator", "time_step": 9}
        entry = store(self.memory, make_incident("INC001", "R001", actions=[action]))
        self.assertEqual(entry["characterization"]["human_action"]["items"], [action])

    def test_recommendation_is_preserved(self):
        entry = store(self.memory, make_incident("INC001", "R001", recommendation="Inspect battery"))
        self.assertEqual(entry["characterization"]["recommendation"]["text"], "Inspect battery")

    def test_limitations_are_preserved(self):
        entry = store(self.memory, make_incident("INC001", "R001"))
        self.assertEqual(entry["evidence"]["limitations"], ["Diagnosis unavailable"])

    def test_unavailable_diagnosis_remains_unavailable(self):
        entry = store(self.memory, make_incident("INC001", "R001", diagnosis=None))
        self.assertEqual(entry["characterization"]["diagnosis"]["status"], "UNAVAILABLE")
        self.assertIsNone(entry["characterization"]["diagnosis"]["possible_failure_type"])

    def test_no_invented_telemetry_or_hidden_simulator_fields(self):
        report = make_incident("INC001", "R001")
        report["observations"] = [{"field": "battery_level", "value": 18.0, "type": "OBSERVATION"}]
        report["observations"].append({"field": "battery_stress", "value": 0.8, "type": "OBSERVATION"})
        report["outcome"]["details"] = {"failure_type": "battery", "repair": "replaced"}
        entry = store(self.memory, report)
        self.assertEqual(len(entry["evidence"]["observations"]), 1)
        self.assertNotIn('"failure_type"', json.dumps(entry))
        self.assertNotIn("battery_stress", json.dumps(entry))

    def test_explanation_includes_memory_context(self):
        store(self.memory, make_incident("INC001", "R001", signals=["critical_battery_level"], outcome={"repair": "battery replaced"}))
        current = make_incident("CURRENT", "R002", status="ACTIVE", signals=["critical_battery_level"])
        context = self.memory.historical_context(current)
        self.assertEqual(context["status"], "AVAILABLE")
        self.assertIn("same_engineering_signal", context["incidents"][0]["similarity_reasons"])
        self.assertEqual(context["incidents"][0]["outcome"]["details"], {"repair": "battery replaced"})

    def test_explanation_says_memory_unavailable_when_empty(self):
        context = self.memory.historical_context(make_incident("CURRENT", "R003", status="ACTIVE"))
        self.assertEqual(context["status"], "UNAVAILABLE")
        self.assertEqual(context["message"], "historical memory unavailable")
        report = IncidentExplanation.build(make_incident("CURRENT", "R003", status="ACTIVE"), {}, historical_memory=context)
        self.assertEqual(report["historical_memory"]["status"], "UNAVAILABLE")

    def test_explanation_includes_historical_memory_section(self):
        store(self.memory, make_incident("INC001", "R001", signals=["critical_battery_level"]))
        current = make_incident("CURRENT", "R003", status="ACTIVE", signals=["critical_battery_level"])
        context = self.memory.historical_context(current)
        report = IncidentExplanation.build(current, {}, historical_memory=context)
        self.assertEqual(report["historical_memory"]["match_count"], 1)
        self.assertEqual(report["historical_memory"]["incidents"][0]["incident_id"], "INC001")

    def test_memory_does_not_modify_incident_lifecycle(self):
        manager = IncidentManager(History())
        incident = manager.create_incident("R001", 1)
        before = incident.status
        store(self.memory, make_incident("INC001", "R001", status="CLOSED"))
        self.assertEqual(incident.status, before)
        self.assertIs(manager.get_active_incident("R001"), incident)

    def test_memory_does_not_predict_or_recommend(self):
        self.assertFalse(hasattr(self.memory, "predict"))
        self.assertFalse(hasattr(self.memory, "recommend"))

    def test_memory_serializes_and_reloads(self):
        original = store(self.memory, make_incident("INC001", "R001", signals=["critical_battery_level"]))
        serialized = json.dumps(original)
        restored = ReliabilityMemory([json.loads(serialized)])
        self.assertEqual(restored.get_by_id("INC001"), original)

    def test_retrieve_by_status(self):
        store(self.memory, make_incident("INC001", "R001", status="CLOSED"))
        store(self.memory, make_incident("INC002", "R002", status="ACTIVE"))
        self.assertEqual(len(self.memory.by_status("ACTIVE")), 1)

    def test_demonstration_same_signal_without_causal_claim(self):
        store(self.memory, make_incident("INC-001", "R001", signals=["critical_battery_level"], outcome={"repair": "battery replaced"}))
        store(self.memory, make_incident("INC-002", "R002", signals=["critical_battery_level"], status="ACTIVE", outcome=None))
        current = make_incident("CURRENT", "R003", status="ACTIVE", signals=["critical_battery_level"])
        context = self.memory.historical_context(current)
        self.assertEqual(context["match_count"], 2)
        self.assertTrue(all("same_engineering_signal" in item["similarity_reasons"] for item in context["incidents"]))
        encoded = json.dumps(context).lower()
        self.assertNotIn("same_cause", encoded)
        self.assertNotIn("caused_by", encoded)
        self.assertEqual(context["incidents"][1]["outcome"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
