"""Tests for the read-only Robot Predictive Maintenance semantic report."""

import csv
from pathlib import Path
import tempfile
import unittest
from xml.sax.saxutils import escape
import zipfile

from real_data_semantic_report import build_semantic_report, _read_test_conditions


ROOT = Path(__file__).resolve().parent
TRAINING_ROOT = (
    ROOT / "real_data" / "robot-predictive-maintenance"
    / "training_data" / "training_data"
)
WORKBOOK = TRAINING_ROOT / "Test conditions.xlsx"


def _cell(column, row, value):
    reference = f"{column}{row}"
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        return f'<c r="{reference}" t="n"><v>{value}</v></c>'
    return (
        f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value))}</t>'
        f"</is></c>"
    )


def _write_workbook(path, run_rows):
    headers = ["Test id", "Description"] + [f"Motor_{motor}_failure" for motor in range(1, 7)]
    all_rows = [headers] + [
        [item.get("run_id"), item.get("description")]
        + [item.get("failures", {}).get(motor) for motor in range(1, 7)]
        for item in run_rows
    ]
    letters = ["A", "B", "C", "D", "E", "F", "G", "H"]
    row_xml = []
    for row_number, values in enumerate(all_rows, start=1):
        cells = "".join(_cell(letters[index], row_number, value)
                        for index, value in enumerate(values))
        row_xml.append(f'<row r="{row_number}">{cells}</row>')
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(row_xml) + "</sheetData></worksheet>"
    )
    workbook = (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    relationships = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


def _write_csv(root, run_id, motor, rows):
    directory = root / run_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"data_motor_{motor}.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("time", "position", "temperature", "voltage", "label"))
        writer.writeheader()
        writer.writerows(rows)
    return path


class RealDataSemanticReportTests(unittest.TestCase):
    def test_actual_workbook_metadata_is_read_without_optional_packages(self):
        self.assertTrue(WORKBOOK.is_file())
        runs = _read_test_conditions(WORKBOOK)
        self.assertEqual(len(runs), 23)
        self.assertTrue(any(item["description"] == "Pick up and place" for item in runs))
        failed = next(item for item in runs if item["run_id"] == "20240325_155003")
        self.assertTrue(all(failed["failure_values"][str(motor)] == 1 for motor in range(1, 7)))

    def test_label_transitions_failure_alignment_and_temporal_window(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_workbook(root / "Test conditions.xlsx", [
                {"run_id": "PICK-NORMAL", "description": "Pick up and place"},
                {"run_id": "PICK-FAIL", "description": "Pick up and place", "failures": {1: 1}},
                {"run_id": "MULTI", "description": "Not moving", "failures": {1: 1, 2: 1}},
            ])
            _write_csv(root, "PICK-NORMAL", 1, [
                {"time": str(i / 10), "position": str(100 + i),
                 "temperature": str(30 + i), "voltage": str(7000 - i), "label": "0"}
                for i in range(5)
            ])
            _write_csv(root, "PICK-FAIL", 1, [
                {"time": str(i / 10), "position": str(200 + i * 2),
                 "temperature": str(40 + i), "voltage": str(7100 - i * 3),
                 "label": "1" if i >= 3 else "0"}
                for i in range(8)
            ])
            for motor, positive_start in ((1, 3), (2, 5)):
                _write_csv(root, "MULTI", motor, [
                    {"time": str(i / 10), "position": str(i),
                     "temperature": str(50 + i), "voltage": str(7200 + i),
                     "label": "1" if i >= positive_start else "0"}
                    for i in range(8)
                ])

            report = build_semantic_report(root)
            observed = report["observed_data"]
            metadata = report["dataset_metadata"]
            fail_run = next(item for item in metadata["runs_from_test_conditions"]
                            if item["run_id"] == "PICK-FAIL")
            motor = fail_run["motor_label_checks"][0]
            self.assertEqual(motor["positive_observations"], 5)
            self.assertEqual(motor["first_positive_timestamp"], "0.3")
            self.assertEqual(motor["last_positive_timestamp"], "0.7")
            self.assertEqual(motor["label_consistency"], "MARKED_AND_POSITIVE_LABELS_PRESENT")

            transition = next(item for item in observed["label_semantics"]["transitions"]
                              if item["run_id"] == "PICK-FAIL" and item["motor"] == 1)
            self.assertEqual(transition["timestamp"], "0.3")
            temporal = next(item for item in observed["failure_run_temporal_behavior"]
                            if item["run_id"] == "PICK-FAIL" and item["motor"] == 1)
            self.assertEqual(temporal["temperature_before_first_positive"], 42.0)
            self.assertEqual(temporal["temperature_at_first_positive"], 43.0)
            self.assertEqual(len(temporal["transition_window"]), 7)
            self.assertEqual(temporal["voltage_behavior"]["change_from_previous_observation"], -3.0)
            self.assertEqual(temporal["position_behavior"]["change_from_previous_observation"], 2.0)

            multi = next(item for item in observed["cross_motor_failure_label_timing"]
                         if item["run_id"] == "MULTI")
            self.assertEqual(multi["timing_comparison"], "DIFFERENT_TIMES")
            pairs = metadata["named_description_comparisons"]["Pick up and place"]["candidate_pairings"]
            self.assertIn({"no_failure_marked_run": "PICK-NORMAL",
                           "documented_failure_run": "PICK-FAIL"}, pairs)

    def test_report_is_deterministic_and_separates_unknowns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_workbook(root / "Test conditions.xlsx", [
                {"run_id": "R1", "description": "Turning motor 6"},
            ])
            _write_csv(root, "R1", 6, [
                {"time": "1.000", "position": "2", "temperature": "255",
                 "voltage": "7000", "label": "0"},
                {"time": "1.100", "position": "3", "temperature": "201",
                 "voltage": "7001", "label": "0"},
            ])
            one = build_semantic_report(root)
            two = build_semantic_report(root)
        self.assertEqual(one, two)
        self.assertEqual(one["observed_data"]["runs_with_temperature_at_least_200"][0]["count"], 2)
        self.assertIn("Temperature values at or above 200", " ".join(one["inference_unknown"]))
        self.assertIn("Turning motor 6", one["dataset_metadata"]["named_description_comparisons"])


if __name__ == "__main__":
    unittest.main()
