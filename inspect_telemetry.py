"""Inspect a recorded CSV/JSON telemetry file and draft a mapping template.

This utility only profiles fields and sample values. It does not run inference,
connect to a robot, or decide sensor units automatically.
"""
import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

SENSITIVE_NAMES = {
    "label", "target", "ground_truth", "groundtruth", "failure_label",
    "fault_label", "diagnosis_label", "failure", "fault", "outcome",
    "is_failure", "failure_status", "class",
}
TARGETS = {
    "motor_temperature": {"motor_temp", "motor_temperature", "motor_temp_c", "motor_temp_f", "motor_temperature_c", "motor_temperature_f", "temperature_motor"},
    "ambient_temperature": {"ambient_temp", "ambient_temperature", "ambient_temp_c", "ambient_temp_f", "environment_temperature"},
    "battery_temperature": {"battery_temp", "battery_temperature", "battery_temp_c", "battery_temp_f"},
    "battery_level": {"battery_level", "battery_percent", "battery_percentage", "soc", "state_of_charge", "charge_percent"},
    "battery_voltage": {"battery_voltage", "battery_voltage_v", "battery_voltage_mv", "voltage_battery"},
    "battery_current": {"battery_current", "battery_current_a", "battery_current_ma", "current_battery"},
    "power_consumption": {"power", "power_consumption", "power_w", "power_kw", "electrical_power"},
    "voltage_drop": {"voltage_drop", "voltage_drop_v", "voltage_drop_mv"},
    "workload": {"workload", "load_factor", "utilization", "utilisation"},
    "robot_state": {"robot_state", "state", "operating_state", "status"},
}


def _normalize_name(value):
    value = value.rsplit(".", 1)[-1].strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value


def _flatten(value, prefix=""):
    result = {}
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(child, dict) and child:
                result.update(_flatten(child, path))
            else:
                result[path] = child
    return result


def _read_records(path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                raise ValueError("CSV file has no header row")
            rows = list(reader)
            return rows, list(reader.fieldnames)
    if suffix in {".jsonl", ".ndjson"}:
        rows = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc.msg}") from exc
    elif suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON at line {exc.lineno}: {exc.msg}") from exc
        if isinstance(data, dict) and isinstance(data.get("observations"), list):
            data = data["observations"]
        rows = data if isinstance(data, list) else [data]
    else:
        raise ValueError("Unsupported input format; use .csv, .json, .jsonl, or .ndjson")
    if not rows:
        raise ValueError("No records found in input")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("Each JSON telemetry record must be an object")
    fields = sorted(set().union(*(_flatten(row).keys() for row in rows)))
    return rows, fields


def _value_kind(value):
    if value is None or value == "":
        return "missing"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "numeric"
    if isinstance(value, str):
        try:
            float(value)
            return "numeric-like string"
        except ValueError:
            return "text"
    return type(value).__name__


def _get_path(row, path):
    current = row
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _suggest_target(field):
    normalized = _normalize_name(field)
    if normalized in SENSITIVE_NAMES:
        return None
    for target, aliases in TARGETS.items():
        if normalized in aliases:
            return target
    # Conservative hints for common field names; still never chooses a unit.
    if "temperature" in normalized or normalized.endswith("_temp"):
        if "battery" in normalized:
            return "battery_temperature"
        if "ambient" in normalized or "environment" in normalized:
            return "ambient_temperature"
        if "motor" in normalized:
            return "motor_temperature"
    return None


def inspect_telemetry(input_path, sample_limit=3):
    path = Path(input_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Telemetry input file not found: {path}")
    rows, fields = _read_records(path)
    if not rows:
        raise ValueError("No records found in input")
    profiles = []
    for field in fields:
        values = [_get_path(row, field) for row in rows]
        nonmissing = [value for value in values if value not in (None, "")]
        kinds = Counter(_value_kind(value) for value in nonmissing)
        normalized = _normalize_name(field)
        suggestion = _suggest_target(field)
        profiles.append({
            "field": field,
            "non_missing_count": len(nonmissing),
            "missing_count": len(rows) - len(nonmissing),
            "observed_types": dict(kinds),
            "sample_values": nonmissing[:sample_limit],
            "suggested_target": suggestion,
            "requires_unit_choice": bool(suggestion and suggestion != "robot_state"),
            "excluded_from_suggestions_reason": "label-like field; do not map into inference" if normalized in SENSITIVE_NAMES else None,
        })
    timestamp_candidates = [field for field in fields if _normalize_name(field) in {"timestamp", "time", "time_s", "time_ms", "timestamp_s", "timestamp_ms", "timestamp_us", "timestamp_ns", "time_step", "stamp"}]
    return {"input_file": path.name, "format": path.suffix.lower().lstrip("."), "record_count": len(rows), "field_count": len(fields), "timestamp_candidates": timestamp_candidates, "fields": profiles,
            "notice": "Suggestions are name-based hints only. Confirm timestamp meaning, source units, signal semantics, and robot identity before using a generated mapping. This inspection does not run inference."}


def create_mapping_template(profile, output_path, robot_id="replace-with-robot-id"):
    timestamp_field = profile["timestamp_candidates"][0] if profile["timestamp_candidates"] else "CHOOSE_TIMESTAMP_FIELD"
    signals = []
    used_targets = set()
    for field in profile["fields"]:
        target = field["suggested_target"]
        if not target or target in used_targets:
            continue
        used_targets.add(target)
        unit = None if target == "robot_state" else "CHOOSE_SOURCE_UNIT"
        item = {"field": field["field"], "target": target}
        if unit is not None:
            item["unit"] = unit
        else:
            item["unit"] = "state"
        signals.append(item)
    template = {
        "robot": {"robot_id": robot_id, "manufacturer": "Unknown", "robot_type": "Unknown"},
        "timestamp": {"field": timestamp_field, "unit": "CHOOSE_TIMESTAMP_UNIT"},
        "signals": signals,
        "_instructions": [
            "Draft only: edit this file before use.",
            "Choose the correct timestamp unit: s, ms, us, or ns.",
            "Replace every CHOOSE_SOURCE_UNIT with a supported unit for that signal.",
            "Verify signal semantics and source units from documentation; names alone are not proof.",
            "Review label-like and unmapped fields; do not map labels or outcomes into inference."
        ]
    }
    output = Path(output_path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output.resolve()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Recorded CSV/JSON/JSONL/NDJSON file to inspect")
    parser.add_argument("--template-out", help="Optional path to write a draft mapping JSON; it requires review before use")
    parser.add_argument("--sample-limit", type=int, default=3, help="Sample values to display per field (default: 3)")
    args = parser.parse_args(argv)
    if args.sample_limit < 1 or args.sample_limit > 10:
        parser.error("--sample-limit must be between 1 and 10")
    try:
        profile = inspect_telemetry(args.input, args.sample_limit)
        print(f"KORDEX TELEMETRY FILE INSPECTION — {profile['input_file']}")
        print(f"Format: {profile['format']} | Records: {profile['record_count']} | Fields: {profile['field_count']}")
        print("This is a schema inspection only; no inference was run and no robot was contacted.\n")
        if profile["timestamp_candidates"]:
            print("Possible timestamp fields (verify meaning and units): " + ", ".join(profile["timestamp_candidates"]))
        else:
            print("No common timestamp field name found. Select the correct time field manually.")
        print("\nFields:")
        for field in profile["fields"]:
            samples = json.dumps(field["sample_values"], ensure_ascii=False)
            suggestion = field["suggested_target"] or "no suggestion"
            if field["excluded_from_suggestions_reason"]:
                suggestion = "not suggested — " + field["excluded_from_suggestions_reason"]
            unit_note = " (unit must be confirmed)" if field["requires_unit_choice"] else ""
            print(f"- {field['field']}: {field['observed_types'] or {'missing': field['missing_count']}}; missing {field['missing_count']}/{profile['record_count']}; samples={samples}; suggestion={suggestion}{unit_note}")
        print("\nReminder: field-name suggestions do not establish sensor meaning or units.")
        if args.template_out:
            output = create_mapping_template(profile, args.template_out)
            print(f"Draft mapping template: {output}")
            print("Edit and verify the template before passing it to custom_telemetry_import.py.")
        return 0
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
