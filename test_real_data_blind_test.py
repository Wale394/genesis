"""End-to-end blind experiment tests using temporary CSV/XLSX fixtures."""

import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape
import zipfile

import real_data_blind_test as experiment
from genesis import Genesis
from real_robot_dataset_adapter import RealRobotDatasetAdapter


RUN_A = experiment.FAILURE_RUN_ID
RUN_B = experiment.COMPARISON_RUN_ID


def _write_xlsx(path):
    headers = ["Test id", "Description"] + [f"Motor_{motor}_failure" for motor in range(1, 7)]
    rows = [
        headers,
        [RUN_A, "Pick up and place", 1, 1, 1, 1, 1, 1],
        [RUN_B, "Pick up and place", None, None, None, None, None, None],
    ]
    letters = "ABCDEFGH"
    rendered = []
    for row_index, values in enumerate(rows, start=1):
        cells = []
        for column, value in zip(letters, values):
            if value is None:
                continue
            ref = f"{column}{row_index}"
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{ref}" t="n"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
        rendered.append(f'<row r="{row_index}">' + "".join(cells) + "</row>")
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(rendered) + "</sheetData></worksheet>"
    )
    workbook = (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


def _write_run(root, run_id, label_value):
    directory = root / run_id
    directory.mkdir(parents=True, exist_ok=True)
    for motor in range(1, 7):
        path = directory / f"data_motor_{motor}.csv"
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=("time", "position", "temperature", "voltage", "label")
            )
            writer.writeheader()
            for index, temperature in enumerate((38 + motor, 40 + motor, 42 + motor, 45 + motor, 48 + motor, 52 + motor)):
                label = label_value if index >= 3 else "0"
                writer.writerow({
                    "time": f"{1000 + index * 0.1:.1f}",
                    "position": f"{motor * 10 + index}",
                    "temperature": str(temperature),
                    "voltage": f"{7000 + motor * 10 + index}",
                    "label": label,
                })


def _file_hashes(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


class SpyGenesis(Genesis):
    instances = []
    inputs = []
    calls = 0

    def __init__(self):
        super().__init__()
        self.__class__.instances.append(self)

    def investigate(self, telemetry_records, **kwargs):
        records = telemetry_records if isinstance(telemetry_records, list) else [telemetry_records]
        for item in records:
            self.__class__.inputs.append(item)
            self.assert_blind_observation(item)
        self.__class__.calls += 1
        return super().investigate(telemetry_records, **kwargs)

    @staticmethod
    def assert_blind_observation(item):
        assert "label" not in item
        assert "failure_event" not in item
        assert "failure_type" not in item
        assert set(item["telemetry"]) == {"time_step", "motor_temperature"}
        metadata = item["source_metadata"]
        assert "label" not in metadata
        assert not any("failure" in key.lower() for key in metadata)
        assert metadata["unmapped_fields"]["position"] is not None
        assert metadata["unmapped_fields"]["voltage"] is not None


class RealDataBlindExperimentTests(unittest.TestCase):
    def setUp(self):
        SpyGenesis.instances = []
        SpyGenesis.inputs = []
        SpyGenesis.calls = 0
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        _write_xlsx(self.root / "Test conditions.xlsx")
        _write_run(self.root, RUN_A, "1")
        _write_run(self.root, RUN_B, "0")

    def tearDown(self):
        self.temp.cleanup()

    def test_ground_truth_is_not_loaded_during_blind_genesis_processing(self):
        with patch.object(RealRobotDatasetAdapter, "load_ground_truth",
                          side_effect=AssertionError("ground truth loaded too early")), \
             patch.object(experiment, "Genesis", SpyGenesis):
            blind = experiment.build_blind_genesis_results(self.root)
        self.assertEqual(len(blind), 12)
        self.assertEqual(len(SpyGenesis.instances), 12)
        self.assertEqual(SpyGenesis.calls, 12)
        self.assertEqual(len(SpyGenesis.inputs), 72)

    def test_output_has_separate_blind_and_post_hoc_sections(self):
        before = _file_hashes(self.root)
        with tempfile.TemporaryDirectory() as output_dir:
            output = Path(output_dir) / "blind.json"
            with patch.object(experiment, "Genesis", SpyGenesis):
                result = experiment.run_blind_experiment(self.root, output)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), result)
        after = _file_hashes(self.root)
        self.assertEqual(before, after)
        sections = result["sections"]
        self.assertEqual(
            set(sections), {"blind_genesis_results", "post_hoc_ground_truth"}
        )
        blind_records = sections["blind_genesis_results"]["records"]
        posthoc_records = sections["post_hoc_ground_truth"]["records"]
        self.assertEqual(len(blind_records), 12)
        self.assertEqual(len(posthoc_records), 12)
        self.assertFalse(sections["blind_genesis_results"]["ground_truth_loaded"])
        self.assertTrue(sections["post_hoc_ground_truth"]["loaded_after_blind_results"])
        encoded = json.dumps(sections["blind_genesis_results"], sort_keys=True)
        self.assertNotIn('"label":', encoded)
        self.assertNotIn('"failure_event":', encoded)

    def test_runs_and_motors_are_independent_and_timestamps_are_preserved(self):
        with patch.object(experiment, "Genesis", SpyGenesis):
            result = experiment.run_blind_experiment(self.root)
        blind = result["sections"]["blind_genesis_results"]["records"]
        self.assertEqual(
            [(item["run_id"], item["motor_id"]) for item in blind],
            [(run, f"motor_{motor}") for run in (RUN_A, RUN_B) for motor in range(1, 7)],
        )
        self.assertEqual(len({id(instance) for instance in SpyGenesis.instances}), 12)
        self.assertTrue(all(item["observation_count"] == 6 for item in blind))
        self.assertEqual(blind[0]["time_range"], {"first": "1000.0", "last": "1000.5"})
        self.assertEqual(blind[0]["source_metadata"]["source"], "robot_predictive_maintenance_dataset")
        gt_a = next(item for item in result["sections"]["post_hoc_ground_truth"]["records"]
                    if item["run_id"] == RUN_A and item["motor_id"] == "motor_1")
        gt_b = next(item for item in result["sections"]["post_hoc_ground_truth"]["records"]
                    if item["run_id"] == RUN_B and item["motor_id"] == "motor_1")
        self.assertEqual(gt_a["positive_label_count"], 3)
        self.assertTrue(gt_a["dataset_metadata"]["documented_failure"])
        self.assertEqual(gt_b["positive_label_count"], 0)
        self.assertFalse(gt_b["dataset_metadata"]["documented_failure"])


if __name__ == "__main__":
    unittest.main()
