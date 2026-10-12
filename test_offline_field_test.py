"""Focused tests for the offline CSV-to-investigation workflow."""

import csv
import json
from pathlib import Path
import tempfile
import unittest

from offline_field_test import run_offline_field_test


class OfflineFieldTestTests(unittest.TestCase):
    def _dataset(self, root, rows):
        run = Path(root) / "RUN-OFFLINE"
        run.mkdir(parents=True)
        path = run / "data_motor_1.csv"
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["time", "position", "temperature", "voltage", "label"])
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_runs_csv_to_session_and_readable_reports_without_labels_in_inference(self):
        with tempfile.TemporaryDirectory() as temp:
            dataset_root = Path(temp) / "dataset"
            dataset_root.mkdir()
            self._dataset(dataset_root, [
                {"time": "1", "position": "0", "temperature": "40", "voltage": "7000", "label": "0"},
                {"time": "2", "position": "1", "temperature": "42", "voltage": "7000", "label": "1"},
                {"time": "3", "position": "2", "temperature": "43", "voltage": "7001", "label": "1"},
            ])
            output = Path(temp) / "output"
            summary = run_offline_field_test(dataset_root, "RUN-OFFLINE", 1, output)

            self.assertEqual(summary["observation_count"], 3)
            self.assertTrue(Path(summary["session_path"]).is_file())
            self.assertTrue(Path(summary["report_json_path"]).is_file())
            self.assertTrue(Path(summary["report_text_path"]).is_file())

            session = json.loads(Path(summary["session_path"]).read_text(encoding="utf-8"))
            self.assertEqual(session["field_test_context"]["mode"], "OFFLINE_RECORDED_DATA")
            self.assertFalse(session["field_test_context"]["live_robot_connection"])
            self.assertNotIn("label", session["observations"][0])
            self.assertNotIn("label", session["observations"][0]["telemetry"])
            self.assertNotIn("label", session["genesis_results"][0]["result"])

            report_text = Path(summary["report_text_path"]).read_text(encoding="utf-8")
            self.assertIn("not a live robot connection", report_text.lower())
            self.assertIn("not a live robot connection or a validated failure prediction", report_text.lower())

    def test_max_observations_bounds_run(self):
        with tempfile.TemporaryDirectory() as temp:
            dataset_root = Path(temp) / "dataset"
            dataset_root.mkdir()
            self._dataset(dataset_root, [
                {"time": "1", "position": "0", "temperature": "40", "voltage": "7000", "label": "0"},
                {"time": "2", "position": "1", "temperature": "42", "voltage": "7000", "label": "0"},
                {"time": "3", "position": "2", "temperature": "43", "voltage": "7001", "label": "0"},
            ])
            summary = run_offline_field_test(dataset_root, "RUN-OFFLINE", 1, Path(temp) / "output", 2)
            self.assertEqual(summary["observation_count"], 2)
            self.assertEqual(summary["time_range"]["last"], "2")

    def test_invalid_limit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "max_observations"):
            run_offline_field_test("unused", "RUN", 1, "unused", 0)


if __name__ == "__main__":
    unittest.main()
