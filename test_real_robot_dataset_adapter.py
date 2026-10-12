"""Focused translation tests for the external predictive-maintenance dataset."""

import csv
from pathlib import Path
import tempfile
import unittest

from real_robot_dataset_adapter import RealRobotDatasetAdapter


ROOT = Path(__file__).resolve().parent
REAL_DATA_ROOT = (
    ROOT / "real_data" / "robot-predictive-maintenance"
    / "training_data" / "training_data"
)
REAL_RUN = "20240325_155003"


def write_motor_csv(directory, motor, rows, columns=("time", "position", "temperature", "voltage", "label")):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"data_motor_{motor}.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


class RealRobotDatasetAdapterTests(unittest.TestCase):
    def test_loads_real_motor_csv_and_preserves_canonical_values(self):
        path = REAL_DATA_ROOT / REAL_RUN / "data_motor_1.csv"
        if not path.is_file():
            self.skipTest(
                "Optional external motor dataset is not included in the public release."
            )
        with path.open("r", newline="", encoding="utf-8") as stream:
            source_rows = list(csv.DictReader(stream))

        adapter = RealRobotDatasetAdapter(REAL_DATA_ROOT, REAL_RUN, 1)
        observations = adapter.load_observations()
        self.assertEqual(len(observations), 6652)
        self.assertEqual(len(observations), len(source_rows))

        first = observations[0]
        self.assertEqual(first["telemetry"]["time_step"], float(source_rows[0]["time"]))
        self.assertEqual(first["source_metadata"]["source_timestamp"], source_rows[0]["time"])
        self.assertEqual(first["identity"]["robot_id"], f"{REAL_RUN}_motor_1")
        self.assertEqual(first["source_metadata"]["run_id"], REAL_RUN)
        self.assertEqual(first["source_metadata"]["motor_id"], "motor_1")
        self.assertEqual(first["telemetry"]["motor_temperature"], float(source_rows[0]["temperature"]))
        self.assertEqual(first["source_metadata"]["original_columns"], list(source_rows[0]))
        self.assertEqual(first["source_metadata"]["unmapped_fields"]["position"], source_rows[0]["position"])
        self.assertEqual(first["source_metadata"]["unmapped_fields"]["voltage"], source_rows[0]["voltage"])
        self.assertNotIn("battery_voltage", first["telemetry"])
        self.assertNotIn("label", first)
        self.assertNotIn("label", first["telemetry"])

    def test_high_temperature_values_are_not_reinterpreted(self):
        if not (REAL_DATA_ROOT / REAL_RUN / "data_motor_1.csv").is_file():
            self.skipTest(
                "Optional external motor dataset is not included in the public release."
            )
        observations = RealRobotDatasetAdapter(REAL_DATA_ROOT, REAL_RUN, 1).load_observations()
        index = next(
            i for i, item in enumerate(observations)
            if item["telemetry"]["motor_temperature"] == 254.0
        )
        item = observations[index]
        self.assertEqual(item["telemetry"]["motor_temperature"], 254.0)
        self.assertEqual(item["source_metadata"]["original_values"]["temperature"], "254")

    def test_ground_truth_is_available_only_through_separate_validation_method(self):
        if not (REAL_DATA_ROOT / REAL_RUN / "data_motor_1.csv").is_file():
            self.skipTest(
                "Optional external motor dataset is not included in the public release."
            )
        adapter = RealRobotDatasetAdapter(REAL_DATA_ROOT, REAL_RUN, 1)
        observation = adapter.load_observations()[0]
        label = adapter.load_ground_truth()[0]
        self.assertEqual(label["timestamp"], observation["source_metadata"]["source_timestamp"])
        self.assertEqual(label["run_id"], REAL_RUN)
        self.assertEqual(label["motor_id"], "motor_1")
        self.assertIn("label", label)
        self.assertNotIn("label", observation)

    def test_multiple_motors_load_independently(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "RUN-A"
            write_motor_csv(run_dir, 1, [{"time": "1.25", "position": "10", "temperature": "42", "voltage": "7000", "label": "0"}])
            write_motor_csv(run_dir, 2, [{"time": "1.25", "position": "20", "temperature": "55", "voltage": "8000", "label": "1"}])
            first = RealRobotDatasetAdapter(temp_dir, "RUN-A", 1).load_observations()[0]
            second = RealRobotDatasetAdapter(temp_dir, "RUN-A", 2).load_observations()[0]
        self.assertEqual(first["identity"]["robot_id"], "RUN-A_motor_1")
        self.assertEqual(second["identity"]["robot_id"], "RUN-A_motor_2")
        self.assertEqual(first["telemetry"]["motor_temperature"], 42.0)
        self.assertEqual(second["telemetry"]["motor_temperature"], 55.0)

    def test_accepts_a_run_directory_as_dataset_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "RUN-B"
            write_motor_csv(run_dir, 3, [{"time": "2.5", "position": "1", "temperature": "45", "voltage": "7100", "label": "0"}])
            item = RealRobotDatasetAdapter(run_dir, "RUN-B", 3).load_observations()[0]
        self.assertEqual(item["source_metadata"]["motor_id"], "motor_3")
        self.assertEqual(item["telemetry"]["time_step"], 2.5)

    def test_missing_csv_has_a_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = RealRobotDatasetAdapter(temp_dir, "MISSING", 1)
            with self.assertRaisesRegex(FileNotFoundError, "run MISSING, motor 1"):
                adapter.load_observations()

    def test_missing_required_columns_has_a_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_motor_csv(
                Path(temp_dir) / "RUN-C", 1,
                [{"time": "1", "label": "0"}], columns=("time", "label"),
            )
            adapter = RealRobotDatasetAdapter(temp_dir, "RUN-C", 1)
            with self.assertRaisesRegex(ValueError, "missing required column.*temperature"):
                adapter.load_observations()

    def test_invalid_numeric_values_are_not_silently_filled_or_changed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_motor_csv(
                Path(temp_dir) / "RUN-D", 1,
                [{"time": "1", "position": "0", "temperature": "hot", "voltage": "7000", "label": "0"}],
            )
            adapter = RealRobotDatasetAdapter(temp_dir, "RUN-D", 1)
            with self.assertRaisesRegex(ValueError, "Invalid numeric value for 'temperature'"):
                adapter.load_observations()


if __name__ == "__main__":
    unittest.main()
