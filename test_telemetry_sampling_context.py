"""Tests for optional, non-causal telemetry sampling context evidence."""

import json
import math
from pathlib import Path
import unittest

from genesis import Genesis
from genesis_field_agent import GenesisFieldAgent
from genesis_field_agent_config import GenesisFieldAgentConfig
from incident_explanation import IncidentExplanation
from telemetry_sampling_context import (
    analyze_sampling_intervals,
    validate_sampling_context,
)


ROOT = Path(__file__).resolve().parent
CONTEXT = {"expected_interval": 1.0, "allowed_jitter": 0.2}
IDENTITY = {"robot_id": "SAMPLE-R1", "manufacturer": "ABB", "robot_type": "AMR"}


def records(times):
    return [{**IDENTITY, "time_step": step, "motor_temperature": 35.0 + index,
             "ambient_temperature": 20.0, "battery_voltage": 48.0,
             "battery_current": 3.0, "battery_level": 80.0, "workload": 25.0}
            for index, step in enumerate(times)]


def evidence_for(result, classification=None):
    items = result["evidence_synthesis"]["sampling_evidence"]
    if classification is None:
        return items
    return [item for item in items if item["supporting_data"]["classification"] == classification]


class TelemetrySamplingContextTests(unittest.TestCase):
    def test_valid_context_is_normalized_and_json_serializable(self):
        context = validate_sampling_context(CONTEXT)
        self.assertEqual(context, CONTEXT)
        self.assertEqual(json.loads(json.dumps(context, allow_nan=False)), CONTEXT)

    def test_zero_interval_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            validate_sampling_context({"expected_interval": 0, "allowed_jitter": 0.2})

    def test_negative_interval_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            validate_sampling_context({"expected_interval": -1, "allowed_jitter": 0.2})

    def test_negative_jitter_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "zero or greater"):
            validate_sampling_context({"expected_interval": 1, "allowed_jitter": -0.1})

    def test_nonfinite_context_values_are_rejected(self):
        for field in ("expected_interval", "allowed_jitter"):
            for value in (math.inf, -math.inf, math.nan):
                invalid = dict(CONTEXT, **{field: value})
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(ValueError, "finite number"):
                        validate_sampling_context(invalid)

    def test_no_context_is_unknown_and_does_not_infer_missing_observations(self):
        result = Genesis().investigate(records([1.0, 2.0, 3.0, 7.0]))
        analysis = result["sampling_analysis"]
        self.assertEqual(analysis["status"], "UNKNOWN")
        self.assertIsNone(analysis["sampling_context"])
        self.assertEqual(analysis["intervals"][-1]["observed_interval"], 4.0)
        self.assertEqual(analysis["intervals"][-1]["classification"], "TIMESTAMP_INTERVAL_OBSERVED")
        self.assertEqual(analysis["possible_gap_count"], 0)
        self.assertFalse(any("lost" in item["statement"].lower() for item in evidence_for(result)))
        self.assertIn("unspecified", analysis["limitations"][0].lower())

    def test_expected_interval_is_normal(self):
        analysis = analyze_sampling_intervals([1.0, 2.0], CONTEXT)
        self.assertEqual(analysis["intervals"][0]["classification"], "NORMAL_INTERVAL")

    def test_jitter_boundary_intervals_are_normal(self):
        intervals = analyze_sampling_intervals([0.0, 0.9, 1.9, 3.0], CONTEXT)["intervals"]
        self.assertEqual([item["observed_interval"] for item in intervals], [0.9, 1.0, 1.1])
        self.assertTrue(all(item["classification"] == "NORMAL_INTERVAL" for item in intervals))

    def test_interval_above_expected_plus_jitter_is_possible_gap(self):
        result = Genesis().investigate(records([1.0, 2.0, 3.0, 4.25]), sampling_context=CONTEXT)
        gap = evidence_for(result, "POSSIBLE_DATA_GAP")
        self.assertEqual(len(gap), 1)
        support = gap[0]["supporting_data"]
        self.assertEqual(support["previous_time_step"], 3)
        self.assertEqual(support["current_time_step"], 4.25)
        self.assertEqual(support["observed_interval"], 1.25)
        self.assertEqual(support["expected_interval"], 1.0)
        self.assertEqual(support["allowed_jitter"], 0.2)
        self.assertEqual(support["excess_interval"], 0.05)
        rendered = json.dumps(gap, allow_nan=False).lower()
        self.assertNotIn("observations were lost", rendered)
        self.assertNotIn("lost_count", rendered)

    def test_multiple_gaps_are_returned_in_chronological_order(self):
        result = Genesis().investigate(records([1.0, 2.0, 3.0, 7.0, 8.0, 12.0]),
                                      sampling_context=CONTEXT)
        gaps = evidence_for(result, "POSSIBLE_DATA_GAP")
        self.assertEqual([
            (item["supporting_data"]["previous_time_step"],
             item["supporting_data"]["current_time_step"])
            for item in gaps
        ], [(3, 7), (8, 12)])
        self.assertEqual(result["sampling_analysis"]["possible_gap_count"], 2)

    def test_irregular_event_driven_stream_without_context_is_not_called_a_gap(self):
        result = Genesis().investigate(records([1.0, 1.1, 3.8, 10.0]))
        self.assertEqual(result["sampling_analysis"]["status"], "UNKNOWN")
        self.assertFalse(evidence_for(result, "POSSIBLE_DATA_GAP"))
        self.assertTrue(all(item["supporting_data"]["sampling_context"] == "UNSPECIFIED"
                            for item in evidence_for(result)))

    def test_ingestion_order_fallback_is_not_treated_as_elapsed_seconds(self):
        stream = [{**IDENTITY, "motor_temperature": 40.0 + index}
                  for index in range(3)]
        result = Genesis().investigate(stream, sampling_context=CONTEXT)
        self.assertEqual(result["sampling_analysis"]["interval_count"], 0)
        self.assertFalse(evidence_for(result))
        self.assertTrue(any("source timestamps" in text
                            for text in result["sampling_analysis"]["limitations"]))

    def test_mixed_timestamp_basis_is_rejected_instead_of_combining_clocks(self):
        first_source = {**IDENTITY, "time_step": 100.0, "motor_temperature": 40.0,
                        "ambient_temperature": 20.0, "battery_voltage": 48.0,
                        "battery_current": 3.0, "battery_level": 80.0, "workload": 25.0}
        missing_source = {**IDENTITY, "motor_temperature": 41.0,
                          "ambient_temperature": 20.0, "battery_voltage": 48.0,
                          "battery_current": 3.0, "battery_level": 80.0, "workload": 25.0}
        with self.assertRaisesRegex(ValueError, "mixed timestamp basis"):
            Genesis().investigate([first_source, missing_source], sampling_context=CONTEXT)

    def test_source_timestamp_after_ingestion_fallback_is_rejected(self):
        missing_source = {**IDENTITY, "motor_temperature": 40.0,
                          "ambient_temperature": 20.0, "battery_voltage": 48.0,
                          "battery_current": 3.0, "battery_level": 80.0, "workload": 25.0}
        later_source = {**IDENTITY, "time_step": 2.0, "motor_temperature": 41.0,
                        "ambient_temperature": 20.0, "battery_voltage": 48.0,
                        "battery_current": 3.0, "battery_level": 80.0, "workload": 25.0}
        with self.assertRaisesRegex(ValueError, "mixed timestamp basis"):
            Genesis().investigate([missing_source, later_source], sampling_context=CONTEXT)

    def test_analysis_and_evidence_are_json_serializable(self):
        result = Genesis().investigate(records([1.0, 2.0, 4.0]), sampling_context=CONTEXT)
        decoded = json.loads(json.dumps(result, allow_nan=False))
        self.assertEqual(decoded["sampling_analysis"]["interval_count"], 2)
        self.assertEqual(len(decoded["evidence_synthesis"]["sampling_evidence"]), 2)

    def test_field_agent_configuration_and_session_context_are_optional(self):
        base = {"session_id": "SAMPLE", "robot_id": "SAMPLE-R1",
                "field_units": {"motor_temperature": "C"}}
        omitted = GenesisFieldAgentConfig.from_dict(base)
        self.assertIsNone(omitted.sampling_context)
        configured = GenesisFieldAgentConfig.from_dict({**base, "sampling_context": CONTEXT,
                                                         "genesis_analysis_enabled": True})
        self.assertEqual(configured.to_dict()["sampling_context"], CONTEXT)
        agent = GenesisFieldAgent(configured)
        for timestamp, temp in ((1, "40 C"), (2, "41 C"), (4, "42 C")):
            agent.ingest_diagnostics({
                "timestamp": timestamp,
                "status": [{"name": "drive", "values": [
                    {"key": "motor_temperature", "value": temp},
                ]}],
            })
        session = agent.get_session()
        self.assertEqual(session["session"]["sampling_context"], CONTEXT)
        self.assertTrue(evidence_for(session["genesis_results"][-1]["result"], "POSSIBLE_DATA_GAP"))
        example = json.loads((ROOT / "GENESIS_FIELD_TEST" / "config.example.json").read_text(encoding="utf-8"))
        self.assertIn("sampling_context", example)
        self.assertIsNone(example["sampling_context"])

    def test_sampling_evidence_is_observational_and_integrated_into_explanation(self):
        result = Genesis().investigate(records([1.0, 2.0, 4.0]), sampling_context=CONTEXT)
        sampling = evidence_for(result, "POSSIBLE_DATA_GAP")
        self.assertEqual(len(sampling), 1)
        self.assertEqual(sampling[0]["evidence_type"], "OBSERVATION")
        self.assertEqual(sampling[0]["source"], "telemetry_sampling_context")
        explanation = IncidentExplanation.build(
            {"robot_id": IDENTITY["robot_id"], "risk": {}},
            feature_record={}, evidence_synthesis=result["evidence_synthesis"],
        )
        self.assertEqual(explanation["evidence_summary"]["sampling_context"],
                         result["evidence_synthesis"]["sampling_evidence"])
        self.assertFalse(any(item["evidence_type"] == "ENGINEERING_SIGNAL" for item in sampling))

    def test_sampling_context_alone_does_not_change_reliability_decision(self):
        stream = records([1.0, 2.0, 3.0, 7.0])
        without_context = Genesis().investigate(stream)
        with_context = Genesis().investigate(stream, sampling_context=CONTEXT)
        self.assertEqual(without_context["reliability_state"], with_context["reliability_state"])
        self.assertEqual(without_context["incident"], with_context["incident"])
        self.assertEqual(without_context["recommendation"], with_context["recommendation"])


if __name__ == "__main__":
    unittest.main()
