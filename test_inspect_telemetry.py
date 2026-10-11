import csv
import json
from pathlib import Path
import tempfile
import unittest

from inspect_telemetry import inspect_telemetry, create_mapping_template


class InspectTelemetryTests(unittest.TestCase):
    def test_csv_profiles_fields_and_does_not_suggest_label(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "robot.csv"
            source.write_text("timestamp_ms,motor_temp_c,label\n1000,40,normal\n2000,41,fault\n", encoding="utf-8")
            profile = inspect_telemetry(source)
            self.assertEqual(profile["record_count"], 2)
            self.assertIn("timestamp_ms", profile["timestamp_candidates"])
            fields = {field["field"]: field for field in profile["fields"]}
            self.assertEqual(fields["motor_temp_c"]["suggested_target"], "motor_temperature")
            self.assertIsNone(fields["label"]["suggested_target"])
            self.assertIn("label-like", fields["label"]["excluded_from_suggestions_reason"])

    def test_nested_json_profiles_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "robot.json"
            source.write_text(json.dumps({"observations": [
                {"time": 1, "sensors": {"battery_voltage": 24}},
                {"time": 2, "sensors": {"battery_voltage": 23.8}},
            ]}), encoding="utf-8")
            profile = inspect_telemetry(source)
            fields = {field["field"]: field for field in profile["fields"]}
            self.assertIn("sensors.battery_voltage", fields)
            self.assertEqual(fields["sensors.battery_voltage"]["suggested_target"], "battery_voltage")

    def test_template_marks_units_for_manual_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "robot.csv"
            source.write_text("time_s,battery_voltage\n1,24\n2,23\n", encoding="utf-8")
            profile = inspect_telemetry(source)
            template_path = create_mapping_template(profile, root / "mapping.json")
            template = json.loads(template_path.read_text(encoding="utf-8"))
            self.assertEqual(template["timestamp"]["field"], "time_s")
            self.assertEqual(template["timestamp"]["unit"], "CHOOSE_TIMESTAMP_UNIT")
            self.assertEqual(template["signals"][0]["unit"], "CHOOSE_SOURCE_UNIT")
            self.assertIn("_instructions", template)

    def test_empty_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "empty.json"
            source.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "No records"):
                inspect_telemetry(source)


if __name__ == "__main__":
    unittest.main()
