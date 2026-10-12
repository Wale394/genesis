"""Run Genesis against recorded motor telemetry and save an engineer-readable report.

This workflow is offline-only. It does not connect to a robot, and it never
loads dataset labels into Genesis inference.
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path

from genesis import Genesis
from investigation_report import build_field_session_report, render_investigation_report
from real_robot_dataset_adapter import RealRobotDatasetAdapter

DEFAULT_DATASET_ROOT = Path(__file__).resolve().parent / "real_data" / "robot-predictive-maintenance"


def run_offline_field_test(dataset_root, run_id, motor_number, output_dir, max_observations=None):
    """Analyze one recorded motor CSV without loading labels or other source fields."""
    if max_observations is not None:
        if isinstance(max_observations, bool) or not isinstance(max_observations, int) or max_observations < 1:
            raise ValueError("max_observations must be a positive integer or None")

    adapter = RealRobotDatasetAdapter(dataset_root, run_id, motor_number)
    observations = adapter.load_observations()
    if max_observations is not None:
        observations = observations[:max_observations]
    if not observations:
        raise ValueError(f"No observations found for run {run_id}, motor {motor_number}")

    # Important: only adapter-produced observations are passed to Genesis.
    # load_ground_truth() is intentionally never called by this workflow.
    engine = Genesis()
    result = engine.investigate(observations)

    first_metadata = observations[0]["source_metadata"]
    last_metadata = observations[-1]["source_metadata"]
    temperatures = [
        item["telemetry"].get("motor_temperature")
        for item in observations
        if item["telemetry"].get("motor_temperature") is not None
    ]
    session = {
        "schema_version": "0.1",
        "session": {
            "session_id": f"OFFLINE-{run_id}-M{motor_number}",
            "robot": deepcopy(observations[0]["identity"]),
            "source": "recorded_csv_benchmark",
            "sampling_context": None,
        },
        "observations": [
            {
                "telemetry": deepcopy(item["telemetry"]),
                "source_metadata": deepcopy(item["source_metadata"]),
                "limitations": deepcopy(item["source_metadata"].get("limitations") or []),
            }
            for item in observations
        ],
        "genesis_results": [{"observation_index": len(observations) - 1, "result": deepcopy(result)}],
        "field_test_context": {
            "mode": "OFFLINE_RECORDED_DATA",
            "live_robot_connection": False,
            "source": first_metadata.get("source"),
            "run_id": run_id,
            "motor_id": f"motor_{motor_number}",
            "observation_count": len(observations),
            "time_range": {
                "first": first_metadata.get("source_timestamp"),
                "last": last_metadata.get("source_timestamp"),
            },
            "motor_temperature_range_celsius_assumed_by_dataset": {
                "minimum": min(temperatures) if temperatures else None,
                "maximum": max(temperatures) if temperatures else None,
            },
            "mapped_fields": ["time_step", "motor_temperature"],
            "excluded_from_inference": ["label", "position", "voltage", "workbook failure metadata"],
            "limitations": [
                "This is recorded benchmark data, not telemetry captured live from a physical robot.",
                "The dataset's temperature unit is not independently authenticated by this adapter; inspect the dataset documentation before interpreting values as Celsius.",
                "Dataset labels and workbook failure metadata were not loaded into the inference path.",
                "Position and voltage remain unmapped because their semantics and units are not established by this adapter.",
                "This run is an exploratory investigation, not validated failure-prediction accuracy or a robot-specific diagnosis.",
            ],
        },
    }
    report = build_field_session_report(session)
    report["field_test_context"] = deepcopy(session["field_test_context"])

    output = Path(output_dir).expanduser()
    output.mkdir(parents=True, exist_ok=True)
    session_path = output / "field-session.json"
    report_json_path = output / "investigation-report.json"
    report_text_path = output / "investigation-report.txt"

    _write_json(session_path, session)
    _write_json(report_json_path, report)
    rendered = render_investigation_report(report)
    disclaimer = [
        "KORDEX OFFLINE FIELD TEST — RECORDED DATA",
        "This is not a live robot connection or a validated failure prediction.",
        "Dataset labels were excluded from Genesis inference. Review field_test_context in the JSON report for mapping and limitations.",
        "",
    ]
    report_text_path.write_text("\n".join(disclaimer) + rendered + "\n", encoding="utf-8")

    return {
        "session_path": str(session_path.resolve()),
        "report_json_path": str(report_json_path.resolve()),
        "report_text_path": str(report_text_path.resolve()),
        "observation_count": len(observations),
        "time_range": session["field_test_context"]["time_range"],
        "temperature_range": session["field_test_context"]["motor_temperature_range_celsius_assumed_by_dataset"],
        "final_reliability_state": (result.get("reliability_state") or {}).get("current"),
    }


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run an offline Genesis investigation on one recorded motor CSV. No robot connection is made."
    )
    parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT), help="Dataset root containing run folders")
    parser.add_argument("--run-id", required=True, help="Recorded dataset run identifier")
    parser.add_argument("--motor", required=True, type=int, help="Motor number, e.g. 1")
    parser.add_argument("--max-observations", type=int, help="Optional positive limit for a bounded run")
    parser.add_argument("--output-dir", default="offline-field-test-output", help="Directory for session and reports")
    args = parser.parse_args(argv)

    summary = run_offline_field_test(
        args.dataset_root, args.run_id, args.motor, args.output_dir, args.max_observations
    )
    print("KORDEX OFFLINE FIELD TEST")
    print("Mode: recorded data; no live robot connection")
    print(f"Run: {args.run_id} | Motor: {args.motor}")
    print(f"Observations analyzed: {summary['observation_count']}")
    print(f"Time range: {summary['time_range']['first']} -> {summary['time_range']['last']}")
    print(f"Temperature range (dataset unit not independently authenticated): {summary['temperature_range']['minimum']} -> {summary['temperature_range']['maximum']}")
    print(f"Final reliability state: {summary['final_reliability_state'] or 'Unavailable'}")
    print(f"Session: {summary['session_path']}")
    print(f"JSON report: {summary['report_json_path']}")
    print(f"Text report: {summary['report_text_path']}")
    print("Reminder: exploratory analysis only; not validated failure prediction.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
