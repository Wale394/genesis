"""Tests for descriptive, non-diagnostic offline report summaries."""
import unittest
from kordex_offline_report_review import build_offline_data_review, render_offline_data_review


class OfflineReportReviewTests(unittest.TestCase):
    def _session(self):
        return {
            "field_test_context": {"mapped_fields": {
                "motor_temp": {"target": "motor_temperature", "source_unit": "C", "canonical_unit": "C"},
                "state": {"target": "robot_state", "source_unit": "state", "canonical_unit": "state"},
            }},
            "observations": [
                {"telemetry": {"time_step": 1.0, "motor_temperature": 30.0, "robot_state": "working"}},
                {"telemetry": {"time_step": 2.0, "motor_temperature": None, "robot_state": "idle"}},
                {"telemetry": {"time_step": 4.0, "motor_temperature": 36.0, "robot_state": "working"}},
            ],
        }

    def test_summary_reports_completeness_range_and_timing_without_diagnosis(self):
        report = build_offline_data_review(self._session())
        temp = report["signals"]["motor_temperature"]
        self.assertEqual(temp["present_count"], 2)
        self.assertEqual(temp["missing_count"], 1)
        self.assertEqual(temp["minimum"], 30.0)
        self.assertEqual(temp["maximum"], 36.0)
        self.assertEqual(temp["net_change"], 6.0)
        self.assertEqual(report["mapped_reading_completeness_percent"], 83.33)
        self.assertEqual(report["time_review"]["maximum_interval_seconds"], 2.0)
        self.assertTrue(report["interpretation_boundary"]["observed_patterns_are_not_confirmed_failures"])
        self.assertTrue(report["interpretation_boundary"]["failure_prediction_is_not_validated_by_this_report"])
        self.assertFalse(any("failure" in key.lower() and "confirmed" in key.lower() for key in temp))

    def test_text_report_explicitly_says_not_diagnosis_and_lists_review_steps(self):
        text = render_offline_data_review(build_offline_data_review(self._session()))
        self.assertIn("not a failure diagnosis", text.lower())
        self.assertIn("No engineering thresholds were applied", text)
        self.assertIn("independent inspection", text)

    def test_empty_session_rejected(self):
        with self.assertRaisesRegex(ValueError, "no observations"):
            build_offline_data_review({"observations": []})


if __name__ == "__main__":
    unittest.main()
