import copy
import json
import unittest

from decision_pipeline import DecisionPipeline
from evidence_synthesis import (
    ENGINEERING_SIGNAL, FLEET_COMPARISON, HISTORICAL_COMPARISON,
    ML_INFERENCE, OBSERVATION, EvidenceSynthesis,
)
from fleet_baseline import FleetBaseline
from history import History
from incident_explanation import IncidentExplanation
from incident_manager import IncidentManager
from recommendation_engine import RecommendationEngine
from reliability_state import ReliabilityState
from evidence_engine import EvidenceEngine
from baseline_engine import BASELINE_ELIGIBLE, BaselineEngine


def sample_inputs(**overrides):
    record = {
        "robot_id": "R004", "manufacturer": "ABB", "robot_type": "AMR",
        "time_step": 10, "motor_temperature": 61.0,
        "ambient_temperature": 25.0, "thermal_rise": 36.0,
        "temperature_change": 17.0, "temperature_rate_3": 20.0,
        "temperature_avg_3": 52.0, "thermal_elevated_persistence": 3,
        "battery_level": 70.0, "battery_voltage": 46.0,
        "battery_current": 12.0, "battery_temperature": 31.0,
        "voltage_drop": 1.2, "power_consumption": 700.0,
        "workload": 55.0, "robot_state": "working",
    }
    quality = {
        "status": "AVAILABLE", "prediction_ready": True,
        "any_major_group_limited": False,
        "history": {"available_prior_observations": 5, "required_prior_observations": 4},
        "groups": {
            name: {"status": "AVAILABLE", "issues": []}
            for name in ("thermal", "battery", "workload")
        },
    }
    risk = {
        "probability": 0.82, "prediction": 1, "model_prediction": 1,
        "prediction_available": True, "fused_risk": "WARNING",
        "engineering": {"status": "signal_detected", "severity": "critical", "signals": [
            {"signal": "critical_motor_temperature", "severity": "critical", "value": 61.0,
             "message": "Critical motor temperature signal detected."},
        ]},
    }
    diagnosis = {"failure_type": "thermal", "probable_cause": "possible thermal issue", "confidence": 0.8}
    recommendation = {"recommendation": "Inspect motor assembly.", "risk_level": "HIGH", "probable_cause": "possible thermal issue"}
    incident = {
        "incident_id": "INC-004", "robot_id": "R004", "site_id": "SITE-1",
        "status": "ACTIVE", "incident_type": "thermal", "start_time_step": 9,
        "end_time_step": None, "actions": [], "outcome": None,
    }
    comparison = {"status": "comparison_available", "metrics": {"temperature_difference": 5.0}}
    baseline = {"status": "baseline_available", "metrics": {"average_motor_temperature": 45.0}}
    fleet = {
        "status": "AVAILABLE", "type": FLEET_COMPARISON,
        "peer_group": {"manufacturer": "ABB", "robot_type": "AMR"},
        "comparable_robot_count": 3, "minimum_peer_count": 2,
        "fleet_pattern": "robot_specific", "limitations": [],
        "metrics": {"motor_temperature": {
            "type": FLEET_COMPARISON, "metric": "motor_temperature", "robot_value": 61.0,
            "peer_count": 3, "peer_mean": 43.0, "peer_minimum": 42.0,
            "peer_maximum": 44.0, "deviation": 18.0, "z_score": 18.0,
            "status": "OUTLIER", "pattern": "robot_specific",
            "interpretation": "Observed motor_temperature is above the range of comparable peers.",
            "limitations": [],
        }},
    }
    memory = {
        "status": "AVAILABLE", "match_count": 2,
        "incidents": [{
            "incident_id": "INC-001", "similarity_reasons": ["same_engineering_signal"],
            "engineering_signals": ["critical_motor_temperature"],
            "diagnosis": {"possible_failure_type": "thermal", "confirmed": False},
            "recommendation": {"text": "Inspect motor"},
            "human_action": {"items": []},
            "outcome": {"status": "RESOLVED", "details": {"repair": "cleaned"}},
        }, {
            "incident_id": "INC-002", "similarity_reasons": ["same_robot_type"],
            "engineering_signals": [], "diagnosis": {"status": "UNAVAILABLE"},
            "recommendation": {"text": None}, "human_action": {"items": []},
            "outcome": {"status": "pending", "details": None},
        }],
    }
    values = {
        "feature_record": record, "observation_quality": quality,
        "risk_result": risk, "diagnosis": diagnosis,
        "recommendation": recommendation, "incident": incident,
        "comparison": comparison, "baseline": baseline,
        "fleet_context": fleet, "historical_memory": memory,
        "timeline": {"events": []},
    }
    values.update(overrides)
    return values


def synthesize(**overrides):
    return EvidenceSynthesis().synthesize(**sample_inputs(**overrides))


class EvidenceSynthesisTests(unittest.TestCase):
    def test_baseline_visibility_exposes_available_metrics(self):
        records = [
            {"motor_temperature": 40.0, "thermal_rise": 2.0,
             "battery_level": 80.0, "baseline_eligibility": BASELINE_ELIGIBLE},
            {"motor_temperature": 44.0, "thermal_rise": 6.0,
             "battery_level": 70.0, "baseline_eligibility": BASELINE_ELIGIBLE},
        ]
        baseline = BaselineEngine(minimum_records=2).build_baseline(records)
        result = synthesize(
            baseline=baseline,
            baseline_visibility={
                "status": "AVAILABLE", "reason": "Baseline is calculated from eligible historical observations.",
                "eligible_records": 2, "required_records": 2, "observed_records": 2,
            },
        )
        self.assertEqual(result["baseline_visibility"]["status"], "AVAILABLE")
        item = next(item for item in result["historical_evidence"]
                    if item["evidence_id"] == "HIST-baseline-status")
        self.assertEqual(item["supporting_data"]["metrics"]["average_motor_temperature"], 42.0)

    def test_unknown_eligibility_is_distinct_from_insufficient_eligible_history(self):
        unknown = synthesize(
            baseline={"status": "insufficient_data", "records_used": 0, "metrics": {}},
            baseline_visibility={
                "status": "ELIGIBILITY_UNKNOWN", "reason": "No explicit eligibility decisions were supplied.",
                "eligible_records": 0, "required_records": 10, "observed_records": 9,
            },
        )
        self.assertEqual(unknown["baseline_visibility"]["status"], "ELIGIBILITY_UNKNOWN")
        self.assertTrue(any("eligibility is unknown" in item["statement"]
                            for item in unknown["historical_evidence"]))
        self.assertTrue(any("no explicit eligibility decisions" in item.lower()
                            for item in unknown["limitations"]))

        insufficient = synthesize(
            baseline={"status": "insufficient_data", "records_used": 2, "metrics": {}},
            baseline_visibility={
                "status": "INSUFFICIENT", "reason": "2 eligible record(s) are available; 10 are required.",
                "eligible_records": 2, "required_records": 10, "observed_records": 4,
            },
        )
        self.assertEqual(insufficient["baseline_visibility"]["status"], "INSUFFICIENT")
        self.assertNotEqual(unknown["baseline_visibility"]["status"], insufficient["baseline_visibility"]["status"])

    def test_observation_evidence(self):
        item = next(item for item in synthesize()["observations"] if item["field"] == "motor_temperature")
        self.assertEqual(item["evidence_type"], OBSERVATION)
        self.assertEqual(item["supporting_data"]["value"], 61.0)

    def test_temporal_evidence(self):
        item = next(item for item in synthesize()["temporal_evidence"] if item["field"] == "temperature_change")
        self.assertIn("17.0", item["statement"])
        self.assertEqual(item["evidence_type"], OBSERVATION)

    def test_engineering_evidence(self):
        result = synthesize()
        self.assertEqual(result["engineering_evidence"][0]["evidence_type"], ENGINEERING_SIGNAL)
        self.assertIn("Critical motor temperature", result["engineering_evidence"][0]["statement"])

    def test_ml_evidence(self):
        item = next(item for item in synthesize()["ml_evidence"] if item["evidence_id"] == "ML-risk")
        self.assertEqual(item["evidence_type"], ML_INFERENCE)
        self.assertIn("0.82", item["statement"])

    def test_fleet_evidence(self):
        item = synthesize()["fleet_evidence"][0]
        self.assertEqual(item["evidence_type"], FLEET_COMPARISON)
        self.assertEqual(item["supporting_data"]["peer_mean"], 43.0)

    def test_historical_evidence(self):
        item = next(item for item in synthesize()["historical_evidence"] if item["evidence_id"] == "HIST-INC-001")
        self.assertEqual(item["evidence_type"], HISTORICAL_COMPARISON)
        self.assertIn("same_engineering_signal", item["statement"])

    def test_observation_quality(self):
        result = synthesize()
        self.assertEqual(result["observation_quality"]["overall"], "AVAILABLE")
        self.assertEqual(result["observation_quality"]["battery"], "AVAILABLE")

    def test_missing_evidence(self):
        values = sample_inputs()
        values["observation_quality"]["history"] = {"available_prior_observations": 1, "required_prior_observations": 4}
        result = EvidenceSynthesis().synthesize(**values)
        self.assertIn("insufficient temporal history", result["missing_evidence"])
        self.assertTrue(result["summary"]["what_we_do_not_know"])

    def test_degraded_evidence(self):
        values = sample_inputs()
        values["observation_quality"]["status"] = "DEGRADED"
        values["observation_quality"]["groups"]["workload"] = {
            "status": "DEGRADED", "issues": [{"check": "unexpected_static_sensor", "fields": ["workload"]}],
        }
        result = EvidenceSynthesis().synthesize(**values)
        self.assertEqual(result["observation_quality"]["workload"], "DEGRADED")
        self.assertIn("workload evidence degraded", result["missing_evidence"])

    def test_unavailable_ml_prediction(self):
        values = sample_inputs()
        values["risk_result"].update(prediction_available=False, probability=None, model_prediction=None, unavailable_reason="warm-up incomplete")
        result = EvidenceSynthesis().synthesize(**values)
        self.assertEqual(result["ml_evidence"][0]["availability"], "UNAVAILABLE")
        self.assertIn("warm-up incomplete", result["missing_evidence"])

    def test_unavailable_diagnosis(self):
        result = synthesize(diagnosis=None)
        self.assertTrue(any(item["statement"] == "Diagnosis unavailable." for item in result["ml_evidence"]))
        self.assertIn("Diagnosis unavailable", result["missing_evidence"])

    def test_unavailable_fleet_comparison(self):
        result = synthesize(fleet_context={"status": "INSUFFICIENT_DATA", "message": "Fleet comparison unavailable: insufficient comparable robots.", "metrics": {}, "limitations": []})
        self.assertEqual(result["fleet_evidence"][0]["availability"], "INSUFFICIENT")
        self.assertTrue(any("Fleet comparison unavailable" in item for item in result["missing_evidence"]))

    def test_unavailable_historical_memory(self):
        result = synthesize(historical_memory={"status": "UNAVAILABLE", "incidents": [], "message": "historical memory unavailable"})
        self.assertIn("historical memory unavailable", result["missing_evidence"])

    def test_contradictions_are_reported_not_resolved(self):
        values = sample_inputs()
        values["risk_result"]["model_prediction"] = 0
        result = EvidenceSynthesis().synthesize(**values)
        contradiction = result["contradictions"][0]
        self.assertIn("disagree", contradiction["statement"])
        self.assertFalse(contradiction["resolved"])

    def test_ml_vs_engineering_disagreement(self):
        result = synthesize()
        self.assertFalse(any(item["contradiction_id"] == "ml-vs-critical-engineering" for item in result["contradictions"]))
        values = sample_inputs()
        values["risk_result"]["model_prediction"] = 0
        self.assertTrue(any(item["contradiction_id"] == "ml-vs-critical-engineering" for item in EvidenceSynthesis().synthesize(**values)["contradictions"]))

    def test_fleet_outlier_can_exist_without_diagnosis(self):
        result = synthesize(diagnosis=None)
        self.assertEqual(result["fleet_evidence"][0]["supporting_data"]["status"], "OUTLIER")
        self.assertTrue(any(item["statement"] == "Diagnosis unavailable." for item in result["ml_evidence"]))

    def test_historical_match_does_not_claim_same_cause(self):
        result = synthesize()
        statements = " ".join(item["statement"] for item in result["historical_evidence"])
        self.assertIn("matched on same_engineering_signal", statements)
        self.assertNotIn("same cause", statements)

    def test_recommendation_is_preserved(self):
        self.assertEqual(synthesize()["recommendation"]["text"], "Inspect motor assembly.")

    def test_human_action_is_preserved(self):
        values = sample_inputs()
        values["incident"]["actions"] = [{"action": "inspected", "actor": "operator"}]
        result = EvidenceSynthesis().synthesize(**values)
        self.assertEqual(result["human_action"]["items"][0]["actor"], "operator")

    def test_outcome_is_preserved(self):
        values = sample_inputs()
        values["incident"]["status"] = "CLOSED"
        values["incident"]["outcome"] = {"repair": "motor replaced"}
        result = EvidenceSynthesis().synthesize(**values)
        self.assertEqual(result["outcome"]["details"], {"repair": "motor replaced"})
        self.assertEqual(result["outcome"]["status"], "RESOLVED")

    def test_no_invented_telemetry(self):
        record = {"robot_id": "R1", "battery_level": 56}
        result = EvidenceSynthesis().synthesize(feature_record=record)
        self.assertEqual([item["field"] for item in result["observations"]], ["battery_level"])

    def test_no_invented_diagnosis(self):
        result = synthesize(diagnosis=None)
        self.assertIsNone(next(item for item in result["ml_evidence"] if item["evidence_id"] == "ML-diagnosis-unavailable")["supporting_data"].get("failure_type"))

    def test_no_invented_outcome(self):
        result = synthesize()
        self.assertEqual(result["outcome"]["status"], "OUTCOME_PENDING")
        self.assertIsNone(result["outcome"]["details"])

    def test_evidence_types_remain_distinct(self):
        result = synthesize()
        types = {item["evidence_type"] for key in (
            "observations", "temporal_evidence", "engineering_evidence",
            "ml_evidence", "fleet_evidence", "historical_evidence",
        ) for item in result[key]}
        self.assertEqual(types, {OBSERVATION, ENGINEERING_SIGNAL, ML_INFERENCE, FLEET_COMPARISON, HISTORICAL_COMPARISON})

    def test_repeated_synthesis_is_deterministic(self):
        one = json.dumps(synthesize(), sort_keys=True)
        two = json.dumps(synthesize(), sort_keys=True)
        self.assertEqual(one, two)

    def test_synthesis_is_json_serializable(self):
        result = synthesize()
        self.assertEqual(json.loads(json.dumps(result)), result)

    def test_incident_explanation_consumes_synthesized_result(self):
        values = sample_inputs()
        synthesis = EvidenceSynthesis().synthesize(**values)
        report = IncidentExplanation.build(
            {"robot_id": "R004", "state": "WARNING", "risk": values["risk_result"]},
            values["feature_record"], incident=values["incident"],
            evidence_synthesis=synthesis,
            historical_memory=values["historical_memory"], fleet_context=values["fleet_context"],
        )
        self.assertIs(report["evidence_synthesis"], synthesis)
        self.assertEqual(report["observations"], synthesis["observations"])
        self.assertEqual(report["contradictions"], synthesis["contradictions"])

    def test_decision_pipeline_integration(self):
        from test_decision_pipeline import DecisionPipelineTests
        fixture = DecisionPipelineTests()
        fixture.setUp()
        pipeline = fixture.make_pipeline(0.75, 1)
        result = fixture.evaluate_at(pipeline, 5)
        self.assertIn("evidence_synthesis", result)
        self.assertEqual(result["explanation"]["evidence_synthesis"], result["evidence_synthesis"])

    def test_synthesis_does_not_modify_fusion_output(self):
        values = sample_inputs()
        values["risk_result"]["fusion"] = {"final": {"risk": "WARNING", "prediction": 1}, "engineering": values["risk_result"]["engineering"]}
        before = copy.deepcopy(values["risk_result"]["fusion"])
        EvidenceSynthesis().synthesize(**values)
        self.assertEqual(values["risk_result"]["fusion"], before)

    def test_synthesis_does_not_modify_incident_manager_lifecycle(self):
        manager = IncidentManager(History())
        incident = manager.create_incident("R004", 1)
        values = sample_inputs(incident=incident)
        EvidenceSynthesis().synthesize(**values)
        self.assertEqual(incident.status, "OPEN")
        self.assertIs(manager.get_active_incident("R004"), incident)

    def test_investigation_summary_answers_requested_questions(self):
        summary = synthesize()["summary"]
        for field in (
            "what_changed", "what_is_unusual", "what_we_have_seen_before",
            "what_the_model_says", "what_we_do_not_know",
            "what_happened_after_recommendation",
        ):
            self.assertIn(field, summary)

    def test_scenario_demonstration_keeps_sources_separate(self):
        result = synthesize()
        self.assertEqual(result["observations"][0]["evidence_type"], OBSERVATION)
        self.assertEqual(result["fleet_evidence"][0]["evidence_type"], FLEET_COMPARISON)
        self.assertEqual(result["engineering_evidence"][0]["evidence_type"], ENGINEERING_SIGNAL)
        self.assertEqual(next(item for item in result["ml_evidence"] if item["evidence_id"] == "ML-risk")["evidence_type"], ML_INFERENCE)
        self.assertTrue(any(item["evidence_type"] == HISTORICAL_COMPARISON for item in result["historical_evidence"]))
        self.assertEqual(result["outcome"]["status"], "OUTCOME_PENDING")


if __name__ == "__main__":
    unittest.main()

class EvidenceLineageTests(unittest.TestCase):
    def test_engine_declares_conservative_field_value_link_for_critical_signal(self):
        result = synthesize()
        signal = next(item for item in result["engineering_evidence"] if item["evidence_id"] == "ENG-0-critical_motor_temperature")
        self.assertEqual(signal["input_evidence_ids"], ["OBS-motor_temperature"])
        self.assertEqual(signal["lineage_relationship"], "FIELD_VALUE_MATCH_NOT_CAUSATION")
        graph = result["evidence_lineage"]
        self.assertTrue(any(edge["from_evidence_id"] == "OBS-motor_temperature" and edge["to_evidence_id"] == signal["evidence_id"] for edge in graph["edges"]))
        self.assertTrue(any("not causation" in limitation.lower() for limitation in graph["limitations"]))

    def test_contradiction_lineage_uses_only_explicit_supporting_ids(self):
        values = sample_inputs()
        values["risk_result"]["model_prediction"] = 0
        result = EvidenceSynthesis().synthesize(**values)
        contradiction = next(item for item in result["contradictions"] if item["contradiction_id"] == "ml-vs-critical-engineering")
        graph = result["evidence_lineage"]
        edges = [edge for edge in graph["edges"] if edge["to_evidence_id"] == contradiction["contradiction_id"]]
        self.assertEqual({edge["from_evidence_id"] for edge in edges}, set(contradiction["supporting_evidence_ids"]))
        self.assertTrue(all(edge["relationship"] == "SUPPORTS_CONTRADICTION" for edge in edges))

    def test_lineage_does_not_claim_unavailable_relationships(self):
        result = synthesize()
        graph = result["evidence_lineage"]
        self.assertEqual(graph["schema_version"], "1.2")
        self.assertIn(graph["status"], {"PARTIAL", "LINKED"})
        self.assertGreater(graph["counts"]["unlinked_evidence"], 0)
        self.assertFalse(any(edge["relationship"] == "CAUSAL" for edge in graph["edges"]))
        self.assertIn("FIELD_VALUE_MATCH_NOT_CAUSATION", [edge["relationship"] for edge in graph["edges"]])

    def test_lineage_exposes_temporal_scope_and_checks_comparable_time_steps(self):
        result = synthesize()
        graph = result["evidence_lineage"]
        observation = next(node for node in graph["nodes"] if node["evidence_id"] == "OBS-motor_temperature")
        self.assertEqual(observation["temporal"]["scope"], "SINGLE_OBSERVATION")
        edge = next(edge for edge in graph["edges"] if edge["from_evidence_id"] == "OBS-motor_temperature")
        self.assertEqual(edge["temporal_order"]["status"], "NOT_AFTER_DEPENDENT")
        self.assertIn("temporal_order_warnings", graph)

    def test_lineage_flags_upstream_measurement_later_than_dependent_evidence(self):
        items = [
            {"evidence_id": "OBS-late", "evidence_type": OBSERVATION,
             "supporting_data": {"time_step": 20, "temporal_scope": "SINGLE_OBSERVATION"}},
            {"evidence_id": "ENG-earlier", "evidence_type": ENGINEERING_SIGNAL,
             "input_evidence_ids": ["OBS-late"],
             "supporting_data": {"evaluation_time_step": 10}},
        ]
        graph = EvidenceSynthesis._build_evidence_lineage(items, [])
        self.assertEqual(graph["counts"]["temporal_order_warnings"], 1)
        self.assertEqual(graph["temporal_order_warnings"][0]["status"], "TEMPORAL_ORDER_CONFLICT")

class PatternWindowLineageTests(unittest.TestCase):
    def test_embedded_pattern_window_rows_become_explicit_graph_links(self):
        values = sample_inputs()
        values["risk_result"]["engineering"]["signals"] = []
        values["telemetry_patterns"] = {
            "status": "AVAILABLE",
            "window_size": 3,
            "patterns": [{
                "pattern": "SUSTAINED_RISE",
                "domain": "thermal",
                "description": "Motor temperature increased across the window.",
                "observations": [
                    {"time_step": 8, "motor_temperature": 58.0, "ambient_temperature": 25.0, "workload": 50.0},
                    {"time_step": 9, "motor_temperature": 61.0, "ambient_temperature": 25.0, "workload": 55.0},
                    {"time_step": 10, "motor_temperature": 63.0, "ambient_temperature": 25.0, "workload": 60.0},
                ],
                "metrics": {"measurement": "motor_temperature"},
            }],
        }
        values["feature_record"]["time_step"] = 10
        values["feature_record"]["motor_temperature"] = 63.0
        values["feature_record"]["ambient_temperature"] = 25.0
        values["feature_record"]["workload"] = 60.0
        result = EvidenceSynthesis().synthesize(**values)
        graph = result["evidence_lineage"]
        self.assertGreater(graph["counts"]["edges"], 0)
        self.assertEqual(graph["schema_version"], "1.2")
        self.assertTrue(any(edge["relationship"] == "OBSERVED_IN_PATTERN_WINDOW" for edge in graph["edges"]))
        self.assertTrue(any(edge["relationship"] == "FIELD_VALUE_MATCH_AT_TIME_STEP" and edge["from_evidence_id"] == "OBS-motor_temperature" for edge in graph["edges"]))
        self.assertFalse(any(edge["relationship"] == "CAUSAL" for edge in graph["edges"]))
        self.assertLess(graph["counts"]["unlinked_evidence"], graph["counts"]["nodes"])

    def test_no_window_edges_are_invented_without_embedded_rows(self):
        values = sample_inputs()
        values["risk_result"]["engineering"]["signals"] = []
        values["telemetry_patterns"] = {"status": "AVAILABLE", "patterns": [{
            "pattern": "OPAQUE_PATTERN", "description": "Pattern with no source rows", "metrics": {}
        }]}
        result = EvidenceSynthesis().synthesize(**values)
        graph = result["evidence_lineage"]
        pattern_id = next(item["evidence_id"] for item in result["pattern_evidence"] if item["evidence_id"].startswith("PATTERN-OPAQUE_PATTERN"))
        self.assertFalse(any(edge["to_evidence_id"] == pattern_id for edge in graph["edges"]))
