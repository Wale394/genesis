"""Focused tests for user-configured recorded CSV/JSON telemetry import."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from custom_telemetry_import import CustomTelemetryImporter, run_custom_telemetry_investigation


class CustomTelemetryImportTests(unittest.TestCase):
    def _config(self, root, signals=None, timestamp=None, robot=None, **extra):
        config = {
            "robot": robot or {"robot_id": "test-robot", "manufacturer": "Example", "robot_type": "mobile"},
            "timestamp": timestamp or {"field": "time_ms", "unit": "ms"},
            "signals": signals or [
                {"field": "temp_f", "target": "motor_temperature", "unit": "F"},
                {"field": "battery_mv", "target": "battery_voltage", "unit": "mV"},
            ],
        }
        config.update(extra)
        path = Path(root) / "mapping.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def test_csv_maps_units_excludes_unmapped_and_generates_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "robot.csv"
            with data.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["time_ms", "temp_f", "battery_mv", "label", "debug"])
                writer.writeheader()
                writer.writerows([
                    {"time_ms": "1000", "temp_f": "212", "battery_mv": "24000", "label": "failure", "debug": "x"},
                    {"time_ms": "2000", "temp_f": "98.6", "battery_mv": "23900", "label": "normal", "debug": "y"},
                ])
            config = self._config(root)
            importer = CustomTelemetryImporter(data, config)
            observations = importer.load_observations()
            self.assertEqual(observations[0]["telemetry"]["time_step"], 1.0)
            self.assertEqual(observations[0]["telemetry"]["motor_temperature"], 100.0)
            self.assertEqual(observations[0]["telemetry"]["battery_voltage"], 24.0)
            self.assertNotIn("label", observations[0]["telemetry"])
            self.assertIn("label", observations[0]["source_metadata"]["unmapped_source_fields"])
            summary = run_custom_telemetry_investigation(data, config, root / "out")
            self.assertEqual(summary["observation_count"], 2)
            self.assertTrue(Path(summary["report_text_path"]).is_file())
            report = json.loads(Path(summary["report_json_path"]).read_text(encoding="utf-8"))
            self.assertEqual(report["field_test_context"]["provenance_status"], "USER_PROVIDED_RECORDED_DATA_NOT_AUTHENTICATED")

    def test_json_nested_fields_and_fraction_battery_level(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "robot.json"
            data.write_text(json.dumps({"observations": [
                {"t": 1, "sensors": {"temp": 300.0, "charge": 0.8}},
                {"t": 2, "sensors": {"temp": 301.0, "charge": 0.79}},
            ]}), encoding="utf-8")
            config = self._config(root,
                timestamp={"field": "t", "unit": "s"},
                signals=[
                    {"field": "sensors.temp", "target": "motor_temperature", "unit": "K"},
                    {"field": "sensors.charge", "target": "battery_level", "unit": "fraction"},
                ])
            observations = CustomTelemetryImporter(data, config).load_observations()
            self.assertAlmostEqual(observations[0]["telemetry"]["motor_temperature"], 26.85)
            self.assertEqual(observations[0]["telemetry"]["battery_level"], 80.0)

    def test_jsonl_records_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "robot.jsonl"
            data.write_text('{"t":1,"temp":30}\n{"t":2,"temp":31}\n', encoding="utf-8")
            config = self._config(root, timestamp={"field": "t", "unit": "s"},
                signals=[{"field": "temp", "target": "motor_temperature", "unit": "C"}])
            self.assertEqual(len(CustomTelemetryImporter(data, config).load_observations()), 2)

    def test_label_like_source_mapping_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "robot.csv"
            data.write_text("t,label\n1,1\n", encoding="utf-8")
            config = self._config(root, timestamp={"field": "t", "unit": "s"},
                signals=[{"field": "label", "target": "workload", "unit": "unitless"}])
            with self.assertRaisesRegex(ValueError, "target leakage"):
                CustomTelemetryImporter(data, config)

    def test_unknown_unit_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "robot.csv"
            data.write_text("t,temp\n1,30\n", encoding="utf-8")
            config = self._config(root, timestamp={"field": "t", "unit": "s"},
                signals=[{"field": "temp", "target": "motor_temperature", "unit": "degrees"}])
            with self.assertRaisesRegex(ValueError, "requires unit"):
                CustomTelemetryImporter(data, config)

    def test_nonmonotonic_timestamps_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "robot.csv"
            data.write_text("t,temp\n2,30\n1,31\n", encoding="utf-8")
            config = self._config(root, timestamp={"field": "t", "unit": "s"},
                signals=[{"field": "temp", "target": "motor_temperature", "unit": "C"}])
            with self.assertRaisesRegex(ValueError, "not later than previous timestamp"):
                CustomTelemetryImporter(data, config).load_observations()

    def test_missing_signal_row_rejected_instead_of_empty_inference(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "robot.csv"
            data.write_text("t,temp\n1,\n", encoding="utf-8")
            config = self._config(root, timestamp={"field": "t", "unit": "s"},
                signals=[{"field": "temp", "target": "motor_temperature", "unit": "C"}])
            with self.assertRaisesRegex(ValueError, "all configured telemetry signals are missing"):
                CustomTelemetryImporter(data, config).load_observations()

    def test_duplicate_target_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "robot.csv"
            data.write_text("t,a,b\n1,30,31\n", encoding="utf-8")
            config = self._config(root, timestamp={"field": "t", "unit": "s"}, signals=[
                {"field": "a", "target": "motor_temperature", "unit": "C"},
                {"field": "b", "target": "motor_temperature", "unit": "C"},
            ])
            with self.assertRaisesRegex(ValueError, "Only one source field"):
                CustomTelemetryImporter(data, config)


if __name__ == "__main__":
    unittest.main()
