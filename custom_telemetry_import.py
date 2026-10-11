"""Investigate engineer-supplied CSV/JSON telemetry using an explicit mapping config.

Offline only: this module never connects to a robot and never executes commands.
"""
import argparse
import csv
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from genesis import Genesis
from investigation_report import build_field_session_report, render_investigation_report
from kordex_offline_report_review import build_offline_data_review, render_offline_data_review

SUPPORTED_TARGETS = {
    "motor_temperature", "ambient_temperature", "battery_level", "battery_voltage",
    "battery_current", "battery_temperature", "power_consumption", "voltage_drop",
    "workload", "robot_state",
}
NUMERIC_TARGETS = SUPPORTED_TARGETS - {"robot_state"}
SENSITIVE_LABEL_NAMES = {
    "label", "target", "ground_truth", "groundtruth", "failure_label",
    "fault_label", "diagnosis_label", "failure", "fault", "outcome",
    "is_failure", "failure_status", "class",
}
UNIT_RULES = {
    "motor_temperature": {"C", "F", "K"},
    "ambient_temperature": {"C", "F", "K"},
    "battery_temperature": {"C", "F", "K"},
    "battery_level": {"%", "fraction"},
    "battery_voltage": {"V", "mV"},
    "battery_current": {"A", "mA"},
    "power_consumption": {"W", "kW"},
    "voltage_drop": {"V", "mV"},
    "workload": {"unitless"},
}
TIME_UNITS_TO_SECONDS = {"s": 1.0, "ms": 0.001, "us": 0.000001, "ns": 0.000000001}
STATE_ALIASES = {
    "active": "working", "running": "working", "operating": "working",
    "working": "working", "idle": "idle", "standby": "idle",
}


class CustomTelemetryImporter:
    """Load mapped CSV/JSON records into Genesis' canonical input contract."""

    def __init__(self, input_path, config_path):
        self.input_path = Path(input_path).expanduser().resolve()
        self.config_path = Path(config_path).expanduser().resolve()
        self.config = self._load_config()
        self._validate_config()

    def _load_config(self):
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            raise FileNotFoundError(f"Mapping config not found: {self.config_path}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid mapping config JSON at line {exc.lineno}: {exc.msg}") from exc
        if not isinstance(config, dict):
            raise ValueError("Mapping config must be a JSON object")
        return config

    def _validate_config(self):
        robot = self.config.get("robot")
        timestamp = self.config.get("timestamp")
        signals = self.config.get("signals")
        if not isinstance(robot, dict):
            raise ValueError("Config 'robot' must be an object")
        if not (isinstance(robot.get("robot_id"), str) and robot["robot_id"].strip()):
            raise ValueError("Config robot.robot_id must be a non-empty string")
        if not isinstance(timestamp, dict) or not isinstance(timestamp.get("field"), str) or not timestamp["field"].strip():
            raise ValueError("Config timestamp.field must name the source timestamp field")
        if timestamp.get("unit") not in TIME_UNITS_TO_SECONDS:
            raise ValueError("Config timestamp.unit must be one of: s, ms, us, ns")
        if not isinstance(signals, list) or not signals:
            raise ValueError("Config signals must be a non-empty list")
        targets = set()
        for index, signal in enumerate(signals):
            if not isinstance(signal, dict):
                raise ValueError(f"Config signals[{index}] must be an object")
            source = signal.get("field")
            target = signal.get("target")
            if not isinstance(source, str) or not source.strip():
                raise ValueError(f"Config signals[{index}].field must be a non-empty source field name")
            if not isinstance(target, str) or target not in SUPPORTED_TARGETS:
                raise ValueError(f"Config signals[{index}].target must be one of: {', '.join(sorted(SUPPORTED_TARGETS))}")
            leaf = source.rsplit(".", 1)[-1].strip().lower().replace("-", "_").replace(" ", "_")
            if leaf in SENSITIVE_LABEL_NAMES:
                raise ValueError(f"Mapping label-like field {source!r} into inference is blocked to prevent target leakage")
            if target in targets:
                raise ValueError(f"Only one source field may map to target {target!r}")
            targets.add(target)
            unit = signal.get("unit")
            if target in NUMERIC_TARGETS and unit not in UNIT_RULES[target]:
                allowed = ", ".join(sorted(UNIT_RULES[target]))
                raise ValueError(f"Config signals[{index}] for {target} requires unit one of: {allowed}")
            if target == "robot_state" and unit not in (None, "state"):
                raise ValueError("robot_state mapping unit must be omitted or 'state'")
        if not (targets & NUMERIC_TARGETS or "robot_state" in targets):
            raise ValueError("At least one supported telemetry signal must be mapped")

    def load_observations(self):
        rows, source_columns = self._load_rows()
        if not rows:
            raise ValueError(f"No records found in {self.input_path.name}")
        observations = []
        previous_timestamp = None
        signals = self.config["signals"]
        mapped_source_paths = {item["field"] for item in signals}
        timestamp_field = self.config["timestamp"]["field"]
        all_source_fields = set(source_columns)
        all_source_fields.add(timestamp_field)
        if self.config["robot"].get("robot_id_field"):
            all_source_fields.add(self.config["robot"]["robot_id_field"])
        for index, row in enumerate(rows, start=1):
            timestamp_raw = _get_path(row, timestamp_field)
            timestamp_value = _finite_number(timestamp_raw, f"timestamp field {timestamp_field!r}", index)
            timestamp = timestamp_value * TIME_UNITS_TO_SECONDS[self.config["timestamp"]["unit"]]
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                raise ValueError(f"Record {index}: timestamp {timestamp:g}s is not later than previous timestamp {previous_timestamp:g}s; input must be chronological with strictly increasing timestamps")
            previous_timestamp = timestamp
            telemetry = {"time_step": timestamp}
            mapped_units = {}
            present_targets = []
            for signal in signals:
                raw = _get_path(row, signal["field"])
                target = signal["target"]
                if raw is None or raw == "":
                    telemetry[target] = None
                    mapped_units[target] = signal.get("unit")
                    continue
                if target == "robot_state":
                    if not isinstance(raw, str):
                        raise ValueError(f"Record {index}: {target} must be a string state")
                    state = STATE_ALIASES.get(raw.strip().lower())
                    if state is None:
                        raise ValueError(f"Record {index}: unsupported robot_state {raw!r}; supported values include working/running/active and idle/standby")
                    telemetry[target] = state
                else:
                    number = _finite_number(raw, f"{target} from {signal['field']!r}", index)
                    telemetry[target] = _convert_unit(number, target, signal["unit"])
                    if target == "battery_level" and not 0 <= telemetry[target] <= 100:
                        raise ValueError(f"Record {index}: battery_level must be between 0 and 100 after unit conversion")
                mapped_units[target] = _canonical_unit(target)
                present_targets.append(target)
            if not present_targets:
                raise ValueError(f"Record {index}: all configured telemetry signals are missing; refusing to analyze an empty observation")
            robot_cfg = self.config["robot"]
            row_robot_id = _get_path(row, robot_cfg["robot_id_field"]) if robot_cfg.get("robot_id_field") else None
            robot_id = str(row_robot_id if row_robot_id not in (None, "") else robot_cfg["robot_id"])
            unknown_fields = sorted(name for name in all_source_fields if name not in mapped_source_paths and name != timestamp_field)
            metadata = {
                "source": "user_supplied_recorded_file",
                "source_file": self.input_path.name,
                "source_format": self.input_path.suffix.lower().lstrip("."),
                "record_index": index,
                "source_timestamp": timestamp_raw,
                "normalized_timestamp_seconds": timestamp,
                "timestamp_source_unit": self.config["timestamp"]["unit"],
                "mapped_fields": {item["field"]: item["target"] for item in signals},
                "canonical_units": mapped_units,
                "unmapped_source_fields": unknown_fields,
                "provenance_status": "USER_PROVIDED_RECORDED_DATA_NOT_AUTHENTICATED",
                "limitations": [
                    "Input is user-provided recorded data; KORDEX has not authenticated the physical source.",
                    "Only explicitly mapped fields enter inference; unmapped fields are excluded.",
                    "Units are declared by the mapping configuration and are not independently verified against the sensor.",
                    "An observed pattern is not proof of a physical failure or a validated failure prediction.",
                ],
            }
            observations.append({
                "identity": {
                    "robot_id": robot_id,
                    "manufacturer": robot_cfg.get("manufacturer"),
                    "robot_type": robot_cfg.get("robot_type"),
                },
                "telemetry": telemetry,
                "source_metadata": metadata,
                "limitations": deepcopy(metadata["limitations"]),
            })
        return observations

    def _load_rows(self):
        suffix = self.input_path.suffix.lower()
        try:
            if suffix == ".csv":
                with self.input_path.open("r", newline="", encoding="utf-8-sig") as stream:
                    reader = csv.DictReader(stream)
                    columns = reader.fieldnames or []
                    if not columns:
                        raise ValueError("CSV file has no header row")
                    rows = []
                    for index, row in enumerate(reader, start=2):
                        if None in row:
                            raise ValueError(f"CSV row {index} has more values than the header")
                        rows.append(row)
                    return rows, columns
            if suffix in (".json", ".jsonl", ".ndjson"):
                if suffix in (".jsonl", ".ndjson"):
                    rows = []
                    for line_no, line in enumerate(self.input_path.read_text(encoding="utf-8-sig").splitlines(), start=1):
                        if not line.strip():
                            continue
                        try:
                            rows.append(json.loads(line))
                        except json.JSONDecodeError as exc:
                            raise ValueError(f"Invalid JSON on line {line_no}: {exc.msg}") from exc
                else:
                    try:
                        data = json.loads(self.input_path.read_text(encoding="utf-8-sig"))
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"Invalid JSON at line {exc.lineno}: {exc.msg}") from exc
                    records_path = self.config.get("records_path")
                    if records_path:
                        data = _get_path(data, records_path)
                    elif isinstance(data, dict) and isinstance(data.get("observations"), list):
                        data = data["observations"]
                    rows = data if isinstance(data, list) else [data]
                if any(not isinstance(row, dict) for row in rows):
                    raise ValueError("Each JSON telemetry record must be an object")
                columns = sorted({path for row in rows for path in _leaf_paths(row)})
                return rows, columns
            raise ValueError("Unsupported input format; use .csv, .json, .jsonl, or .ndjson")
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Telemetry input file not found: {self.input_path}") from exc


def _leaf_paths(value, prefix=""):
    paths = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(child, dict) and child:
                paths.extend(_leaf_paths(child, path))
            else:
                paths.append(path)
    return paths


def _get_path(value, path):
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _finite_number(value, description, index):
    if isinstance(value, bool) or value is None or value == "":
        raise ValueError(f"Record {index}: missing numeric {description}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Record {index}: {description} must be numeric, got {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"Record {index}: {description} must be finite, got {value!r}")
    return number


def _convert_unit(value, target, unit):
    if target in ("motor_temperature", "ambient_temperature", "battery_temperature"):
        if unit == "F":
            return (value - 32.0) * 5.0 / 9.0
        if unit == "K":
            return value - 273.15
        return value
    if target == "battery_level" and unit == "fraction":
        return value * 100.0
    if target in ("battery_voltage", "voltage_drop") and unit == "mV":
        return value / 1000.0
    if target == "battery_current" and unit == "mA":
        return value / 1000.0
    if target == "power_consumption" and unit == "kW":
        return value * 1000.0
    return value


def _canonical_unit(target):
    return {
        "motor_temperature": "C", "ambient_temperature": "C", "battery_temperature": "C",
        "battery_level": "%", "battery_voltage": "V", "battery_current": "A",
        "power_consumption": "W", "voltage_drop": "V", "workload": "unitless",
        "robot_state": "state",
    }[target]


def run_custom_telemetry_investigation(input_path, config_path, output_dir):
    importer = CustomTelemetryImporter(input_path, config_path)
    observations = importer.load_observations()
    engine = Genesis()
    result = engine.investigate(observations)
    first, last = observations[0], observations[-1]
    session = {
        "schema_version": "0.1",
        "session": {
            "session_id": "CUSTOM-OFFLINE-" + importer.input_path.stem,
            "robot": deepcopy(first["identity"]),
            "source": "user_supplied_recorded_file",
            "sampling_context": None,
        },
        "observations": [
            {"identity": deepcopy(item["identity"]), "telemetry": deepcopy(item["telemetry"]),
             "source_metadata": deepcopy(item["source_metadata"]), "limitations": deepcopy(item["limitations"])}
            for item in observations
        ],
        "genesis_results": [{"observation_index": len(observations) - 1, "result": deepcopy(result)}],
        "field_test_context": {
            "mode": "OFFLINE_USER_SUPPLIED_RECORDED_DATA",
            "live_robot_connection": False,
            "source_file": importer.input_path.name,
            "source_format": importer.input_path.suffix.lower().lstrip("."),
            "observation_count": len(observations),
            "time_range_seconds": {"first": first["telemetry"]["time_step"], "last": last["telemetry"]["time_step"]},
            "mapped_fields": {item["field"]: {"target": item["target"], "source_unit": item.get("unit"), "canonical_unit": _canonical_unit(item["target"])} for item in importer.config["signals"]},
            "unmapped_source_fields": sorted(set().union(*(set(item["source_metadata"]["unmapped_source_fields"]) for item in observations))),
            "provenance_status": "USER_PROVIDED_RECORDED_DATA_NOT_AUTHENTICATED",
            "limitations": deepcopy(observations[-1]["limitations"]),
        },
    }
    report = build_field_session_report(session)
    report["field_test_context"] = deepcopy(session["field_test_context"])
    report["offline_data_review"] = build_offline_data_review(session)
    out = Path(output_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    session_path = out / "field-session.json"
    report_json_path = out / "investigation-report.json"
    report_text_path = out / "investigation-report.txt"
    session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    report_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    report_text_path.write_text(
        "KORDEX OFFLINE INVESTIGATION — USER-PROVIDED RECORDED DATA\n"
        "No live robot connection was made. Source identity and sensor units are not independently authenticated.\n"
        "Observed patterns are not proof of physical failure or validated failure prediction.\n\n"
        + render_investigation_report(report) + "\n"
        + render_offline_data_review(report["offline_data_review"]) + "\n", encoding="utf-8"
    )
    return {
        "observation_count": len(observations),
        "robot_id": first["identity"]["robot_id"],
        "time_range_seconds": session["field_test_context"]["time_range_seconds"],
        "session_path": str(session_path.resolve()),
        "report_json_path": str(report_json_path.resolve()),
        "report_text_path": str(report_text_path.resolve()),
        "mapped_fields": session["field_test_context"]["mapped_fields"],
        "unmapped_source_fields": session["field_test_context"]["unmapped_source_fields"],
        "final_reliability_state": (result.get("reliability_state") or {}).get("current"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Recorded telemetry .csv, .json, .jsonl, or .ndjson file")
    parser.add_argument("--config", required=True, help="Explicit JSON mapping config")
    parser.add_argument("--output-dir", default="custom-telemetry-output", help="Directory for session and reports")
    args = parser.parse_args(argv)
    summary = run_custom_telemetry_investigation(args.input, args.config, args.output_dir)
    print("KORDEX CUSTOM TELEMETRY INVESTIGATION")
    print("Mode: offline recorded data; no live robot connection")
    print(f"Robot ID: {summary['robot_id']}")
    print(f"Observations analyzed: {summary['observation_count']}")
    print(f"Time range (seconds): {summary['time_range_seconds']['first']} -> {summary['time_range_seconds']['last']}")
    print(f"Mapped signals: {', '.join(summary['mapped_fields'])}")
    print(f"Unmapped source fields: {', '.join(summary['unmapped_source_fields']) or 'none'}")
    print(f"Final reliability state: {summary['final_reliability_state'] or 'Unavailable'}")
    print(f"Session: {summary['session_path']}")
    print(f"JSON report: {summary['report_json_path']}")
    print(f"Text report: {summary['report_text_path']}")
    print("Reminder: exploratory investigation only; not validated failure prediction.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
