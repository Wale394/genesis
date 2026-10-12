"""Focused tests for first-detection timing in the single-motor blind replay."""
import unittest
from unittest.mock import patch

import research.real_robot.blind_replay_1a as replay


class FirstDetectionTimingTests(unittest.TestCase):
    def test_extracts_current_observation_engineering_signal_and_pattern(self):
        result = {
            "risk": {"engineering": {"signals": [
                {"signal": "critical_motor_temperature", "severity": "critical", "value": 61.0, "message": "detail"}
            ]}},
            "evidence_synthesis": {"pattern_evidence": [
                {"statement": "Temperature increased", "supporting_data": {"pattern": "sustained_rise", "metrics": {"large": "payload"}}}
            ]},
        }
        self.assertEqual(replay._extract_observation_detections(result), {
            "engineering_signals": [{
                "signal": "critical_motor_temperature", "severity": "critical", "value": 61.0,
            }],
            "patterns": [{"pattern": "sustained_rise", "statement": "Temperature increased"}],
        })

    def test_post_hoc_uses_first_detection_not_final_timestamp(self):
        blind = {"blind_results": {
            "run": {"final_timestamp": "20"},
            "engineering_signals": {
                "signals_in_final_result": [{"signal": "critical_motor_temperature"}],
                "first_detection_timestamp": "5",
            },
            "temporal_analysis": {"patterns_detected_in_final_result": []},
            "observation_quality": {"state": "AVAILABLE"},
            "limitations": [],
        }}
        labels = [{"timestamp": "10", "label": 1}]
        with patch.object(replay.RealRobotDatasetAdapter, "load_ground_truth", return_value=labels), \
             patch.object(replay, "_find_workbook", return_value="fixture.xlsx"), \
             patch.object(replay, "_read_test_conditions", return_value=[{
                 "run_id": replay.RUN_ID, "failure_values": {str(replay.MOTOR): 1}
             }]), \
             patch.object(replay, "_is_marked_failure", return_value=True):
            result = replay._post_hoc("unused", blind)
        self.assertEqual(result["first_genesis_detection_timestamp"], "5")
        self.assertEqual(result["signal_timing_classification"], "GENESIS_FIRST_DETECTION_BEFORE_LABEL")
        self.assertIn("does not establish a physical failure time", result["timing_caveat"])

    def test_no_signal_remains_distinct_from_timing_unavailable(self):
        blind = {"blind_results": {
            "run": {"final_timestamp": "20"},
            "engineering_signals": {"signals_in_final_result": [], "first_detection_timestamp": None},
            "temporal_analysis": {"patterns_detected_in_final_result": []},
            "observation_quality": {"state": "AVAILABLE"},
            "limitations": [],
        }}
        labels = [{"timestamp": "10", "label": 1}]
        with patch.object(replay.RealRobotDatasetAdapter, "load_ground_truth", return_value=labels), \
             patch.object(replay, "_find_workbook", return_value="fixture.xlsx"), \
             patch.object(replay, "_read_test_conditions", return_value=[{
                 "run_id": replay.RUN_ID, "failure_values": {str(replay.MOTOR): 1}
             }]), \
             patch.object(replay, "_is_marked_failure", return_value=True):
            result = replay._post_hoc("unused", blind)
        self.assertEqual(result["signal_timing_classification"], "NO_GENESIS_SIGNAL")


if __name__ == "__main__":
    unittest.main()
