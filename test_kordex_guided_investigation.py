import tempfile
import unittest
from pathlib import Path
from inspect_telemetry import inspect_telemetry
from kordex_guided_investigation import build_mapping_config, run_guided_workflow

class GuidedMappingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.csv = self.root / "robot.csv"
        self.csv.write_text("timestamp_ms,motor_temp_c,battery_percent,ground_truth\n1000,42,80,normal\n2000,43,79,fault\n", encoding="utf-8")
        self.profile = inspect_telemetry(self.csv)
    def tearDown(self): self.temp.cleanup()
    def test_builds_explicit_mapping(self):
        config = build_mapping_config(self.profile, "robot-1", "Maker", "AMR", "timestamp_ms", "ms", [{"field":"motor_temp_c","target":"motor_temperature","unit":"C"},{"field":"battery_percent","target":"battery_level","unit":"%"}])
        self.assertEqual(config["timestamp"]["unit"], "ms")
        self.assertEqual(config["signals"][0]["target"], "motor_temperature")
    def test_blocks_label_mapping(self):
        with self.assertRaisesRegex(ValueError, "label-like"):
            build_mapping_config(self.profile, "robot-1", "Unknown", "Unknown", "timestamp_ms", "ms", [{"field":"ground_truth","target":"robot_state","unit":"state"}])
    def test_rejects_unknown_timestamp(self):
        with self.assertRaisesRegex(ValueError, "not present"):
            build_mapping_config(self.profile, "robot-1", "Unknown", "Unknown", "bad", "s", [{"field":"motor_temp_c","target":"motor_temperature","unit":"C"}])
    def test_rejects_reusing_one_source_field_for_multiple_targets(self):
        with self.assertRaisesRegex(ValueError, "multiple targets"):
            build_mapping_config(self.profile, "robot-1", "Unknown", "Unknown", "timestamp_ms", "ms", [
                {"field":"motor_temp_c","target":"motor_temperature","unit":"C"},
                {"field":"motor_temp_c","target":"ambient_temperature","unit":"C"},
            ])
    def test_guided_flow_saves_config_without_running_by_default(self):
        answers = iter(["robot-1", "Maker", "AMR", "timestamp_ms", "ms", "motor_temp_c", "C", "-", "-", "battery_percent", "%", "-", "-", "-", "-", "-", "-", "n"])
        result = run_guided_workflow(self.csv, self.root / "out", input_fn=lambda prompt: next(answers), output_fn=lambda text: None)
        self.assertTrue(Path(result["config_path"]).is_file())
        self.assertIsNone(result["investigation"])
    def test_existing_config_is_not_overwritten(self):
        out = self.root / "out"
        out.mkdir()
        existing = out / "robot.kordex-mapping.json"
        existing.write_text("{}", encoding="utf-8")
        answers = iter(["robot-1", "Unknown", "Unknown", "timestamp_ms", "ms", "motor_temp_c", "C", "-", "-", "battery_percent", "%", "-", "-", "-", "-", "-", "-", "n"])
        with self.assertRaises(FileExistsError):
            run_guided_workflow(self.csv, out, input_fn=lambda prompt: next(answers), output_fn=lambda text: None)

if __name__ == "__main__": unittest.main()
