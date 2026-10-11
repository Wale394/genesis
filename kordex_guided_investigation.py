"""Guided offline workflow to inspect, map, review, and optionally investigate telemetry."""
import argparse
import json
from pathlib import Path
from custom_telemetry_import import NUMERIC_TARGETS, SENSITIVE_LABEL_NAMES, SUPPORTED_TARGETS, UNIT_RULES, run_custom_telemetry_investigation
from inspect_telemetry import inspect_telemetry

TIMESTAMP_UNITS = ("s", "ms", "us", "ns")
TARGET_ORDER = ("motor_temperature", "ambient_temperature", "battery_temperature", "battery_level", "battery_voltage", "battery_current", "power_consumption", "voltage_drop", "workload", "robot_state")


def _is_label_like(field):
    return field.rsplit(".", 1)[-1].strip().lower().replace("-", "_").replace(" ", "_") in SENSITIVE_LABEL_NAMES


def _ask(prompt, input_fn=input, output_fn=print, default=None, required=False):
    suffix = f" [{default}]" if default not in (None, "") else ""
    while True:
        answer = input_fn(f"{prompt}{suffix}: ").strip()
        if not answer and default not in (None, ""):
            return str(default)
        if answer:
            return answer
        if not required:
            return ""
        output_fn("A value is required.")


def _choose_timestamp_field(profile, input_fn=input, output_fn=print):
    fields = [item["field"] for item in profile["fields"]]
    candidates = profile["timestamp_candidates"]
    default = candidates[0] if len(candidates) == 1 else None
    while True:
        answer = _ask("Timestamp field (exact name or candidate number)", input_fn, output_fn, default=default, required=True)
        if answer.isdigit():
            index = int(answer) - 1
            if 0 <= index < len(candidates):
                return candidates[index]
            output_fn("Candidate number is out of range.")
        elif answer in fields:
            return answer
        else:
            output_fn("Field not found. Use an exact field name shown above.")


def _choose_unit(target, input_fn=input, output_fn=print):
    if target == "robot_state":
        return "state"
    choices = sorted(UNIT_RULES[target])
    while True:
        answer = _ask(f"Source unit for {target} ({'/'.join(choices)}; confirm from source docs)", input_fn, output_fn, required=True)
        if answer in UNIT_RULES[target]:
            return answer
        output_fn("Unsupported unit. Choose one of the listed units.")


def build_mapping_config(profile, robot_id, manufacturer, robot_type, timestamp_field, timestamp_unit, signal_mappings):
    known_fields = {item["field"] for item in profile["fields"]}
    if timestamp_field not in known_fields:
        raise ValueError(f"Timestamp field {timestamp_field!r} is not present in the inspected file")
    if timestamp_unit not in TIMESTAMP_UNITS:
        raise ValueError(f"Unsupported timestamp unit {timestamp_unit!r}")
    if not isinstance(robot_id, str) or not robot_id.strip():
        raise ValueError("Robot ID must not be empty")
    signals, seen_targets, seen_fields = [], set(), set()
    for item in signal_mappings:
        field, target, unit = item["field"], item["target"], item["unit"]
        if field not in known_fields:
            raise ValueError(f"Signal field {field!r} is not present in the inspected file")
        if _is_label_like(field):
            raise ValueError(f"Refusing to map label-like field {field!r} into inference")
        if target not in SUPPORTED_TARGETS:
            raise ValueError(f"Unsupported KORDEX target {target!r}")
        if target in seen_targets:
            raise ValueError(f"Only one source field may map to target {target!r}")
        if field in seen_fields:
            raise ValueError(f"Source field {field!r} cannot map to multiple targets")
        if target in NUMERIC_TARGETS and unit not in UNIT_RULES[target]:
            raise ValueError(f"Unsupported unit {unit!r} for {target}")
        if target == "robot_state" and unit != "state":
            raise ValueError("robot_state unit must be 'state'")
        seen_targets.add(target)
        seen_fields.add(field)
        signals.append({"field": field, "target": target, "unit": unit})
    if not signals:
        raise ValueError("Choose at least one supported signal before running an investigation")
    return {"robot": {"robot_id": robot_id.strip(), "manufacturer": manufacturer or "Unknown", "robot_type": robot_type or "Unknown"}, "timestamp": {"field": timestamp_field, "unit": timestamp_unit}, "signals": signals}


def run_guided_workflow(input_path, output_dir="kordex-guided-output", config_out=None, overwrite_config=False, input_fn=input, output_fn=print):
    profile = inspect_telemetry(input_path)
    output_fn(f"\nKORDEX GUIDED OFFLINE INVESTIGATION — {profile['input_file']}")
    output_fn(f"Format: {profile['format']} | Records: {profile['record_count']} | Fields: {profile['field_count']}")
    output_fn("No robot connection will be made. Name-based suggestions are hints, not proof of signal meaning or units.\n")
    for index, field in enumerate(profile["fields"], 1):
        suggestion = field["suggested_target"] or "none"
        if field["excluded_from_suggestions_reason"]:
            suggestion = "blocked label/outcome field"
        output_fn(f"{index}. {field['field']} | missing {field['missing_count']}/{profile['record_count']} | samples {json.dumps(field['sample_values'], ensure_ascii=False)} | suggestion {suggestion}")
    robot_id = _ask("Robot/asset identifier (user-provided label, not authenticated identity)", input_fn, output_fn, required=True)
    manufacturer = _ask("Manufacturer (optional; Enter for Unknown)", input_fn, output_fn, default="Unknown")
    robot_type = _ask("Robot type (optional; Enter for Unknown)", input_fn, output_fn, default="Unknown")
    timestamp_field = _choose_timestamp_field(profile, input_fn, output_fn)
    while True:
        timestamp_unit = _ask("Timestamp unit (s/ms/us/ns; verify from source docs)", input_fn, output_fn, required=True)
        if timestamp_unit in TIMESTAMP_UNITS:
            break
        output_fn("Choose s, ms, us, or ns.")
    profiles_by_target = {}
    for item in profile["fields"]:
        if item["suggested_target"] and not item["excluded_from_suggestions_reason"]:
            profiles_by_target.setdefault(item["suggested_target"], []).append(item["field"])
    known_fields = {item["field"] for item in profile["fields"]}
    mappings = []
    output_fn("\nMap fields to supported signals. Enter '-' to skip. Confirm every source unit.")
    for target in TARGET_ORDER:
        suggested = profiles_by_target.get(target, [])
        default = suggested[0] if len(suggested) == 1 else None
        hint = f" (suggestion: {', '.join(suggested)})" if suggested else ""
        while True:
            field = _ask(f"Source field for {target}{hint}; '-' skips", input_fn, output_fn, default=default)
            if field == "-" or not field:
                break
            if field not in known_fields:
                output_fn("Field not found. Enter an exact field name or '-'.")
                continue
            if _is_label_like(field):
                output_fn("Label/outcome fields cannot be mapped into inference.")
                continue
            mappings.append({"field": field, "target": target, "unit": _choose_unit(target, input_fn, output_fn)})
            break
    config = build_mapping_config(profile, robot_id, manufacturer, robot_type, timestamp_field, timestamp_unit, mappings)
    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    config_path = Path(config_out).expanduser().resolve() if config_out else out_dir / f"{Path(input_path).stem}.kordex-mapping.json"
    if config_path.exists() and not overwrite_config:
        raise FileExistsError(f"Mapping config already exists: {config_path}. Choose --config-out or use --overwrite-config to replace it.")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    output_fn(f"\nDraft mapping saved: {config_path}")
    output_fn("Review the proposed mapping below. Verify field meaning, timestamp semantics, units, and asset metadata before analysis:")
    output_fn(json.dumps(config, indent=2, ensure_ascii=False))
    run_now = _ask("Run the offline investigation now? [y/N]", input_fn, output_fn, default="N").lower() in {"y", "yes"}
    if not run_now:
        output_fn("No inference run. The mapping is saved for review.")
        return {"config_path": str(config_path), "investigation": None}
    summary = run_custom_telemetry_investigation(input_path, config_path, out_dir)
    output_fn("\nInvestigation complete. Recorded data only; source identity and units are not independently authenticated.")
    output_fn(f"Observations: {summary['observation_count']}")
    output_fn(f"Text report: {summary['report_text_path']}")
    output_fn(f"JSON report: {summary['report_json_path']}")
    return {"config_path": str(config_path), "investigation": summary}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Recorded CSV/JSON/JSONL/NDJSON file")
    parser.add_argument("--output-dir", default="kordex-guided-output", help="Directory for mapping and reports")
    parser.add_argument("--config-out", help="Optional explicit path for the mapping JSON")
    parser.add_argument("--overwrite-config", action="store_true", help="Allow replacing an existing mapping file")
    args = parser.parse_args(argv)
    try:
        run_guided_workflow(args.input, args.output_dir, args.config_out, args.overwrite_config)
        return 0
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
