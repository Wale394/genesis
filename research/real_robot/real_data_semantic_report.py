"""Read-only semantic inspection of the Robot Predictive Maintenance data.

This is an offline dataset audit. It does not call Genesis inference and does
not interpret labels as physical causes.
"""

import argparse
from collections import Counter, defaultdict
import json
import math
import posixpath
from pathlib import Path
import re
import statistics
import zipfile
import xml.etree.ElementTree as ET

from real_robot_dataset_adapter import RealRobotDatasetAdapter


XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
TRANSITION_WINDOW_RADIUS = 3
MOTOR_NUMBERS = tuple(range(1, 7))
SENSORS = ("temperature", "voltage", "position")


def build_semantic_report(dataset_root):
    """Inspect the training run directory and its test-condition workbook."""
    root = Path(dataset_root).expanduser()
    workbook = _find_workbook(root)
    csv_root = workbook.parent
    metadata_runs = _read_test_conditions(workbook)

    all_files = {}
    for path in csv_root.rglob("data_motor_*.csv"):
        match = re.fullmatch(r"data_motor_(\d+)\.csv", path.name)
        if match:
            all_files[(path.parent.name, int(match.group(1)))] = path

    labels = Counter()
    label_rows = 0
    label_missing = 0
    label_non_finite = 0
    sensor_stats = {
        motor: {
            field: {"minimum": None, "maximum": None, "missing_values": 0,
                    "non_finite_values": 0, "nonnumeric_values": 0,
                    "finite_values": 0}
            for field in SENSORS
        }
        for motor in MOTOR_NUMBERS
    }
    motor_run_labels = []
    label_transitions = []
    high_temperature_runs = []
    raw_summary_by_run_motor = {}

    for (run_id, motor), path in sorted(all_files.items()):
        result = _inspect_motor_file(path, run_id, motor)
        raw_summary_by_run_motor[(run_id, motor)] = result
        for field in SENSORS:
            target = sensor_stats[motor][field]
            source = result["sensor_counts"][field]
            target["missing_values"] += source["missing_values"]
            target["non_finite_values"] += source["non_finite_values"]
            target["nonnumeric_values"] += source["nonnumeric_values"]
            target["finite_values"] += source["finite_values"]
            values = result["sensor_finite_ranges"][field]
            if values["minimum"] is not None:
                target["minimum"] = _min_or_value(target["minimum"], values["minimum"])
                target["maximum"] = _max_or_value(target["maximum"], values["maximum"])

        labels.update(result["label_counts"])
        label_rows += result["label_observation_count"]
        label_missing += result["label_missing_values"]
        label_non_finite += result["label_non_finite_values"]
        motor_run_labels.append(result["label_behavior"])
        label_transitions.extend(result["label_transitions"])
        if result["high_temperature"]["count"]:
            high_temperature_runs.append(result["high_temperature"])

    run_reports = []
    failure_temporal = []
    cross_motor_timing = []
    for metadata in metadata_runs:
        run_id = metadata["run_id"]
        motor_statuses = []
        marked_motor_temporals = []
        for motor in MOTOR_NUMBERS:
            marked_value = metadata["failure_values"].get(str(motor))
            marked = _is_marked_failure(marked_value)
            summary = raw_summary_by_run_motor.get((run_id, motor))
            if summary is None:
                status = {
                    "motor": motor,
                    "failure_value_in_metadata": marked_value,
                    "marked_as_failure": marked,
                    "csv_present": False,
                    "positive_observations": None,
                    "first_positive_timestamp": None,
                    "last_positive_timestamp": None,
                    "label_consistency": "CSV_UNAVAILABLE",
                }
                motor_statuses.append(status)
                if marked:
                    marked_motor_temporals.append({
                        "run_id": run_id, "motor": motor,
                        "status": "CSV_UNAVAILABLE",
                    })
                continue

            positive = summary["positive_labels"]
            count = len(positive)
            if marked and count:
                consistency = "MARKED_AND_POSITIVE_LABELS_PRESENT"
            elif marked:
                consistency = "MARKED_BUT_NO_POSITIVE_LABELS"
            elif count:
                consistency = "NOT_MARKED_BUT_POSITIVE_LABELS_PRESENT"
            else:
                consistency = "NOT_MARKED_AND_NO_POSITIVE_LABELS"
            status = {
                "motor": motor,
                "failure_value_in_metadata": marked_value,
                "marked_as_failure": marked,
                "csv_present": True,
                "positive_observations": count,
                "first_positive_timestamp": positive[0]["timestamp"] if positive else None,
                "last_positive_timestamp": positive[-1]["timestamp"] if positive else None,
                "label_consistency": consistency,
            }
            motor_statuses.append(status)
            if marked:
                temporal = _failure_temporal_behavior(summary)
                marked_motor_temporals.append(temporal)
                failure_temporal.append(temporal)

        run_report = {
            "run_id": run_id,
            "description": metadata["description"],
            "motors_marked_as_failure": [
                motor for motor in MOTOR_NUMBERS
                if _is_marked_failure(metadata["failure_values"].get(str(motor)))
            ],
            "motor_label_checks": motor_statuses,
        }
        run_reports.append(run_report)
        if len(run_report["motors_marked_as_failure"]) > 1:
            cross_motor_timing.append(
                _cross_motor_timing(run_id, marked_motor_temporals)
            )

    description_groups = _description_comparisons(metadata_runs)
    named_comparisons = {}
    for description in ("Pick up and place", "Not moving", "Turning motor 6"):
        match = next((group for group in description_groups
                      if group["normalized_description"] == _normalize_description(description)), None)
        named_comparisons[description] = match or {
            "description": description,
            "same_description_groups_found": False,
            "documented_failure_runs": [],
            "no_failure_marked_runs": [],
            "candidate_pairings": [],
        }

    for motor in MOTOR_NUMBERS:
        for field in SENSORS:
            sensor_stats[motor][field].pop("finite_values", None)
        sensor_stats[motor]["total_missing_values"] = sum(
            sensor_stats[motor][field]["missing_values"] for field in SENSORS
        )
        sensor_stats[motor]["total_non_finite_values"] = sum(
            sensor_stats[motor][field]["non_finite_values"] for field in SENSORS
        )
        sensor_stats[motor]["total_nonnumeric_values"] = sum(
            sensor_stats[motor][field]["nonnumeric_values"] for field in SENSORS
        )
        field_stats = {
            field: sensor_stats[motor][field] for field in SENSORS
        }
        sensor_stats[motor] = {"sensors": field_stats, **{
            key: sensor_stats[motor][key]
            for key in ("total_missing_values", "total_non_finite_values", "total_nonnumeric_values")
        }}

    distinct_labels = [
        {"value": _json_label(value), "count": count,
         "percentage": round(100.0 * count / label_rows, 6) if label_rows else 0.0}
        for value, count in sorted(labels.items(), key=lambda item: _label_sort_key(item[0]))
    ]
    metadata_failure_count = sum(
        bool(item["motors_marked_as_failure"]) for item in run_reports
    )
    return {
        "report_version": "0.1",
        "source": {
            "dataset_root": str(csv_root.resolve()),
            "test_conditions_workbook": str(workbook.resolve()),
            "scope": "training dataset only",
        },
        "methodology": {
            "positive_label_value": "numeric label equal to 1",
            "label_percentage_denominator": "all non-missing label cells",
            "label_transition_rule": "Adjacent non-missing label values in CSV row order; each transition is reported at the destination row timestamp.",
            "transition_window_radius_observations": TRANSITION_WINDOW_RADIUS,
            "approximately_same_cross_motor_time_rule": "First-positive timestamp spread no greater than the maximum median positive sampling interval among compared motors.",
            "description_grouping_rule": "Exact match after case-folding and collapsing non-alphanumeric separators; no fuzzy similarity inference.",
            "timestamps": "Reported from source cells; numeric timestamp comparisons are used only for cross-motor timing.",
        },
        "observed_data": {
            "label_semantics": {
                "distinct_values": distinct_labels,
                "labeled_observations": label_rows,
                "missing_labels": label_missing,
                "non_finite_labels": label_non_finite,
                "constant_or_changing_by_run_motor": sorted(
                    motor_run_labels, key=lambda item: (item["run_id"], item["motor"])
                ),
                "transitions": sorted(
                    label_transitions,
                    key=lambda item: (item["run_id"], item["motor"], item["row_index"]),
                ),
            },
            "sensor_ranges_by_motor": {
                f"motor_{motor}": sensor_stats[motor] for motor in MOTOR_NUMBERS
            },
            "runs_with_temperature_at_least_200": sorted(
                high_temperature_runs, key=lambda item: (item["run_id"], item["motor"])
            ),
            "failure_run_temporal_behavior": sorted(
                failure_temporal, key=lambda item: (item["run_id"], item["motor"])
            ),
            "cross_motor_failure_label_timing": sorted(
                cross_motor_timing, key=lambda item: item["run_id"]
            ),
        },
        "dataset_metadata": {
            "runs_from_test_conditions": run_reports,
            "description_comparisons": description_groups,
            "named_description_comparisons": named_comparisons,
            "metadata_runs_marking_at_least_one_failure": metadata_failure_count,
        },
        "inference_unknown": [
            "A blank failure cell means no motor is marked as failed in the workbook; it does not establish a confirmed normal run.",
            "CSV labels are reported as observed ground truth values only; their physical meaning and generation rule are not established by this report.",
            "Agreement or disagreement between workbook failure flags and CSV labels is descriptive and does not establish causality.",
            "Temperature values at or above 200 are listed without classifying them as valid readings or missing-value sentinels.",
            "Motor voltage units and semantics are not specified; position and voltage remain raw dataset fields outside the current Genesis observation contract.",
            "A shared timebase or clock synchronization across motors is not established by the workbook or CSV structure.",
        ],
    }


def _inspect_motor_file(path, run_id, motor):
    # Use the existing adapter's path resolution, but inspect source rows here
    # because this audit must count malformed/non-finite values and preserve labels.
    adapter = RealRobotDatasetAdapter(path.parent, run_id, motor)
    if adapter.path.resolve() != path.resolve():
        raise ValueError(f"Resolved motor CSV path did not match requested file: {path}")
    observations = []
    label_counts = Counter()
    label_missing = 0
    label_nonfinite = 0
    positive_labels = []
    previous_label = None
    transitions = []
    sensor_counts = {
        field: {"missing_values": 0, "non_finite_values": 0, "nonnumeric_values": 0,
                "finite_values": 0}
        for field in SENSORS
    }
    sensor_values = {field: [] for field in SENSORS}
    high_indices = []
    columns = []

    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        import csv
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        for row_index, row in enumerate(reader):
            row_number = row_index + 2
            parsed = {}
            for field in SENSORS:
                value, state = _parse_number(row.get(field))
                parsed[field] = value
                sensor_counts[field][{
                    "missing": "missing_values",
                    "non_finite": "non_finite_values",
                    "nonnumeric": "nonnumeric_values",
                }.get(state, "finite_values")] += 1
                if state == "finite":
                    sensor_values[field].append(value)

            raw_label = row.get("label")
            label, label_state = _parse_label(raw_label)
            if label_state == "missing":
                label_missing += 1
            else:
                if label_state == "non_finite":
                    label_nonfinite += 1
                label_counts[label] += 1
                if previous_label is not None and label != previous_label:
                    transitions.append({
                        "run_id": run_id,
                        "motor": motor,
                        "row_index": row_index,
                        "csv_line": row_number,
                        "timestamp": row.get("time"),
                        "from_label": _json_label(previous_label),
                        "to_label": _json_label(label),
                    })
                previous_label = label
                if label_state == "finite" and label == 1:
                    positive_labels.append({
                        "row_index": row_index,
                        "timestamp": row.get("time"),
                    })

            if parsed["temperature"] is not None and parsed["temperature"] >= 200:
                high_indices.append(row_index)
            observations.append({
                "row_index": row_index,
                "timestamp": row.get("time"),
                "temperature": parsed["temperature"],
                "voltage": parsed["voltage"],
                "position": parsed["position"],
                "raw": {field: row.get(field) for field in (*SENSORS, "label")},
                "label": label if label_state == "finite" else None,
            })

    behavior = {
        "run_id": run_id,
        "motor": motor,
        "row_count": len(observations),
        "labeled_observations": sum(label_counts.values()),
        "distinct_label_values": [
            _json_label(value) for value in sorted(label_counts, key=_label_sort_key)
        ],
        "behavior": (
            "NO_LABEL_VALUES" if not label_counts else
            "CONSTANT" if len(label_counts) == 1 else "CHANGES_OVER_TIME"
        ),
        "transition_count": len(transitions),
    }
    ranges = {
        field: {
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
        }
        for field, values in sensor_values.items()
    }
    high = {
        "run_id": run_id,
        "motor": motor,
        "count": len(high_indices),
        "first_timestamp": observations[high_indices[0]]["timestamp"] if high_indices else None,
        "last_timestamp": observations[high_indices[-1]]["timestamp"] if high_indices else None,
        "maximum_temperature": max(
            (observations[index]["temperature"] for index in high_indices), default=None
        ),
    }
    positive_labels.sort(key=lambda item: item["row_index"])
    return {
        "columns": columns,
        "observations": observations,
        "label_counts": label_counts,
        "label_observation_count": sum(label_counts.values()),
        "label_missing_values": label_missing,
        "label_non_finite_values": label_nonfinite,
        "label_behavior": behavior,
        "label_transitions": transitions,
        "positive_labels": positive_labels,
        "sensor_counts": sensor_counts,
        "sensor_finite_ranges": ranges,
        "high_temperature": high,
    }


def _failure_temporal_behavior(summary):
    observations = summary["observations"]
    positives = summary["positive_labels"]
    result = {
        "run_id": summary["label_behavior"]["run_id"],
        "motor": summary["label_behavior"]["motor"],
        "positive_observations": len(positives),
        "first_positive_timestamp": positives[0]["timestamp"] if positives else None,
        "last_positive_timestamp": positives[-1]["timestamp"] if positives else None,
        "beginning_temperature": observations[0]["temperature"] if observations else None,
        "maximum_temperature": summary["sensor_finite_ranges"]["temperature"]["maximum"],
        "median_sampling_interval": _median_sampling_interval(summary),
        "transition_window_radius_observations": TRANSITION_WINDOW_RADIUS,
    }
    if not positives:
        result.update({
            "status": "NO_POSITIVE_LABEL_OBSERVED",
            "temperature_before_first_positive": None,
            "temperature_at_first_positive": None,
            "transition_window": [],
            "voltage_behavior": None,
            "position_behavior": None,
        })
        return result

    first_index = positives[0]["row_index"]
    start = max(0, first_index - TRANSITION_WINDOW_RADIUS)
    end = min(len(observations), first_index + TRANSITION_WINDOW_RADIUS + 1)
    window = observations[start:end]
    previous = observations[first_index - 1] if first_index else None
    at = observations[first_index]
    result.update({
        "status": "AVAILABLE",
        "first_positive_row_index": first_index,
        "temperature_before_first_positive": previous["temperature"] if previous else None,
        "temperature_at_first_positive": at["temperature"],
        "transition_window": [
            {
                "row_index": item["row_index"],
                "offset_from_first_positive": item["row_index"] - first_index,
                "timestamp": item["timestamp"],
                "label": item["label"],
                "temperature": item["temperature"],
                "voltage": item["voltage"],
                "position": item["position"],
                "raw_voltage": item["raw"]["voltage"],
                "raw_position": item["raw"]["position"],
            }
            for item in window
        ],
        "voltage_behavior": _transition_signal_behavior(observations, first_index, "voltage"),
        "position_behavior": _transition_signal_behavior(observations, first_index, "position"),
    })
    return result


def _transition_signal_behavior(observations, index, field):
    before = observations[index - 1][field] if index else None
    at = observations[index][field]
    if before is None or at is None:
        change = None
    else:
        change = at - before
    window = observations[max(0, index - TRANSITION_WINDOW_RADIUS):
                           min(len(observations), index + TRANSITION_WINDOW_RADIUS + 1)]
    return {
        "field": field,
        "before_first_positive": before,
        "at_first_positive": at,
        "change_from_previous_observation": change,
        "values_in_window": [
            {"timestamp": item["timestamp"], "value": item[field], "label": item["label"]}
            for item in window
        ],
        "unit": "unspecified",
    }


def _cross_motor_timing(run_id, marked_motor_temporals):
    positives = [
        item for item in marked_motor_temporals
        if item.get("status") == "AVAILABLE" and item.get("first_positive_timestamp") is not None
    ]
    if len(positives) < 2:
        return {
            "run_id": run_id,
            "status": "INSUFFICIENT_POSITIVE_LABEL_TIMESTAMPS",
            "marked_motors": [item["motor"] for item in marked_motor_temporals],
            "first_positive_labels": [
                {"motor": item["motor"], "timestamp": item.get("first_positive_timestamp")}
                for item in marked_motor_temporals
            ],
            "interpretation": "Not enough marked motors have positive-label timestamps to compare timing.",
        }
    times = [(item["motor"], _finite_float(item["first_positive_timestamp"])) for item in positives]
    times = [(motor, value) for motor, value in times if value is not None]
    if len(times) < 2:
        status = "TIMESTAMPS_NOT_NUMERIC"
        spread = tolerance = None
        timing = None
    else:
        spread = max(value for _, value in times) - min(value for _, value in times)
        intervals = [
            item.get("median_sampling_interval") for item in positives
            if item.get("median_sampling_interval") is not None
        ]
        tolerance = max(intervals) if intervals else 0.0
        timing = "APPROXIMATELY_SAME_TIME" if spread <= tolerance else "DIFFERENT_TIMES"
        status = "COMPARED"
    return {
        "run_id": run_id,
        "status": status,
        "marked_motors": [item["motor"] for item in marked_motor_temporals],
        "first_positive_labels": [
            {"motor": item["motor"], "timestamp": item.get("first_positive_timestamp")}
            for item in marked_motor_temporals
        ],
        "spread_between_first_positive_timestamps": spread,
        "approximate_same_time_tolerance": tolerance,
        "timing_comparison": timing,
        "interpretation": "Timestamp comparison only; no causal relationship is inferred.",
    }


def _description_comparisons(runs):
    groups = defaultdict(list)
    for run in runs:
        description = run["description"]
        if description:
            groups[_normalize_description(description)].append(run)
    result = []
    for normalized, members in sorted(groups.items()):
        marked = [member for member in members if any(
            _is_marked_failure(value) for value in member["failure_values"].values()
        )]
        unmarked = [member for member in members if member not in marked]
        pairings = [
            {"no_failure_marked_run": control["run_id"],
             "documented_failure_run": failed["run_id"]}
            for control in unmarked for failed in marked
        ]
        result.append({
            "normalized_description": normalized,
            "descriptions": sorted({member["description"] for member in members}),
            "runs": [member["run_id"] for member in members],
            "documented_failure_runs": [member["run_id"] for member in marked],
            "no_failure_marked_runs": [member["run_id"] for member in unmarked],
            "candidate_pairings": pairings,
        })
    return result


def _read_test_conditions(path):
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relation_targets = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
        }
        sheets = workbook.find(f"{{{XLSX_NS}}}sheets")
        if sheets is None or not list(sheets):
            raise ValueError(f"Workbook has no worksheets: {path}")
        sheet = list(sheets)[0]
        relation_id = sheet.attrib.get(f"{{{REL_NS}}}id")
        target = relation_targets.get(relation_id)
        if not target:
            raise ValueError(f"Workbook worksheet relationship is missing: {path}")
        sheet_path = posixpath.normpath(
            target.lstrip("/") if target.startswith("/") else posixpath.join("xl", target)
        )
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [
                "".join(node.text or "" for node in item.findall(f".//{{{XLSX_NS}}}t"))
                for item in shared_root.findall(f"{{{XLSX_NS}}}si")
            ]
        sheet_root = ET.fromstring(archive.read(sheet_path))
        sheet_data = sheet_root.find(f"{{{XLSX_NS}}}sheetData")
        rows = []
        if sheet_data is not None:
            for row in sheet_data.findall(f"{{{XLSX_NS}}}row"):
                values = {}
                for cell in row.findall(f"{{{XLSX_NS}}}c"):
                    column = _column_index(cell.attrib.get("r", ""))
                    value_node = cell.find(f"{{{XLSX_NS}}}v")
                    value = value_node.text if value_node is not None else None
                    cell_type = cell.attrib.get("t")
                    if cell_type == "s" and value is not None:
                        value = shared[int(value)]
                    elif cell_type == "inlineStr":
                        value = "".join(
                            node.text or "" for node in cell.findall(f".//{{{XLSX_NS}}}t")
                        )
                    elif cell_type == "b" and value is not None:
                        value = value == "1"
                    elif cell_type == "e":
                        value = {"cell_error": value}
                    elif value is not None and cell_type not in ("str", "s", "inlineStr"):
                        value = _excel_number(value)
                    values[column] = value
                rows.append(values)

    header_row_index = next((i for i, row in enumerate(rows) if row), None)
    if header_row_index is None:
        raise ValueError(f"Workbook sheet is empty: {path}")
    header_cells = rows[header_row_index]
    headers = {index: str(value).strip() for index, value in header_cells.items() if value is not None}
    required = {"Test id", "Description"}
    if not required.issubset(set(headers.values())):
        raise ValueError(f"Workbook is missing required metadata columns: {sorted(required - set(headers.values()))}")
    runs = []
    for row in rows[header_row_index + 1:]:
        values = {headers[column]: value for column, value in row.items() if column in headers}
        run_id = values.get("Test id")
        if run_id in (None, ""):
            continue
        failure_values = {}
        for motor in MOTOR_NUMBERS:
            key = f"Motor_{motor}_failure"
            if key in values:
                failure_values[str(motor)] = values[key]
        runs.append({
            "run_id": str(run_id),
            "description": str(values.get("Description") or "").strip(),
            "failure_values": failure_values,
        })
    return runs


def _find_workbook(root):
    candidates = [
        root / "Test conditions.xlsx",
        root / "training_data" / "Test conditions.xlsx",
        root / "training_data" / "training_data" / "Test conditions.xlsx",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "Test conditions.xlsx not found; searched: "
        + ", ".join(str(item) for item in candidates)
    )


def _parse_number(raw):
    if raw is None or str(raw).strip() == "":
        return None, "missing"
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, "nonnumeric"
    if not math.isfinite(value):
        return None, "non_finite"
    return value, "finite"


def _parse_label(raw):
    if raw is None or str(raw).strip() == "":
        return None, "missing"
    value, state = _parse_number(raw)
    if state == "finite":
        return _normalized_number(value), "finite"
    if state == "non_finite":
        return str(raw).strip(), state
    return str(raw).strip(), "text"


def _normalize_description(description):
    return " ".join(re.findall(r"[a-z0-9]+", str(description).casefold()))


def _is_marked_failure(value):
    if isinstance(value, bool):
        return value
    number, state = _parse_number(value)
    return state == "finite" and number == 1


def _normalized_number(value):
    return int(value) if value.is_integer() else value


def _json_label(value):
    return value


def _label_sort_key(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, float(value))
    return (1, str(value))


def _min_or_value(current, value):
    return value if current is None else min(current, value)


def _max_or_value(current, value):
    return value if current is None else max(current, value)


def _column_index(reference):
    letters = re.match(r"([A-Z]+)", reference)
    if not letters:
        raise ValueError(f"Malformed workbook cell reference: {reference!r}")
    result = 0
    for char in letters.group(1):
        result = result * 26 + ord(char) - ord("A") + 1
    return result


def _excel_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    return _normalized_number(number) if math.isfinite(number) else value


def _finite_float(value):
    parsed, state = _parse_number(value)
    return parsed if state == "finite" else None


def _median_sampling_interval(summary):
    times = [_finite_float(item["timestamp"]) for item in summary["observations"]]
    times = [value for value in times if value is not None]
    intervals = [right - left for left, right in zip(times, times[1:]) if right > left]
    return statistics.median(intervals) if intervals else None


def _human_summary(report):
    labels = report["observed_data"]["label_semantics"]
    metadata = report["dataset_metadata"]
    positives = next((item["count"] for item in labels["distinct_values"] if item["value"] == 1), 0)
    transitions = len(labels["transitions"])
    marked_runs = metadata["metadata_runs_marking_at_least_one_failure"]
    pairings = sum(
        len(item["candidate_pairings"])
        for item in metadata["description_comparisons"]
    )
    return "\n".join([
        "ROBOT PREDICTIVE MAINTENANCE DATA SEMANTIC REPORT",
        "",
        "OBSERVED DATA",
        f"- Labeled observations: {labels['labeled_observations']}",
        f"- Positive label value 1: {positives}",
        f"- Label transitions across run/motor files: {transitions}",
        f"- Motor/run files with temperature >= 200: {len(report['observed_data']['runs_with_temperature_at_least_200'])}",
        "",
        "DATASET METADATA",
        f"- Runs listed in Test conditions.xlsx: {len(metadata['runs_from_test_conditions'])}",
        f"- Runs with at least one motor marked as failure: {marked_runs}",
        f"- Same-description candidate pairings: {pairings}",
        "",
        "INFERENCE / UNKNOWN",
        "- Metadata and labels are reported descriptively; no causes are inferred.",
        "- Blank failure flags are not treated as proof of normal operation.",
    ])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = build_semantic_report(args.dataset_root)
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(_human_summary(report))
    print(f"\nJSON report: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
