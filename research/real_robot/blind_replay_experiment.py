"""Blind Genesis comparison for two Robot Predictive Maintenance runs.

The first phase only loads adapter-produced observations and calls the
existing Genesis API. CSV labels and workbook failure flags are opened only
after every blind run/motor result has been produced.
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path

from genesis import Genesis
from investigation_report import build_investigation_report
from real_robot_dataset_adapter import RealRobotDatasetAdapter
from real_data_semantic_report import _find_workbook, _is_marked_failure, _read_test_conditions


FAILURE_RUN_ID = "20240325_155003"
COMPARISON_RUN_ID = "20240325_152902"
MOTORS = tuple(range(1, 7))


def build_blind_genesis_results(dataset_root, run_ids=(FAILURE_RUN_ID, COMPARISON_RUN_ID)):
    """Run Genesis without loading label values or workbook failure metadata."""
    blind_records = []
    for run_id in run_ids:
        for motor in MOTORS:
            adapter = RealRobotDatasetAdapter(dataset_root, run_id, motor)
            observations = adapter.load_observations()
            if not observations:
                raise ValueError(f"No observations found for run {run_id}, motor {motor}")

            # A separate facade prevents run/motor histories or lifecycle from
            # contaminating the next blind analysis.
            genesis = Genesis()
            # Genesis accepts chronological batches and processes every item
            # through its normal streaming feature/pipeline path. Calling the
            # facade separately for every row would also rebuild its public
            # capability/report output thousands of times per motor.
            final = genesis.investigate(observations)
            report = build_investigation_report(final)
            first_metadata = observations[0]["source_metadata"]
            last_metadata = observations[-1]["source_metadata"]
            telemetry_values = [
                item["telemetry"]["motor_temperature"] for item in observations
                if item["telemetry"].get("motor_temperature") is not None
            ]
            quality = deepcopy(final.get("observation_quality") or {})
            incident = deepcopy(final.get("incident") or {})
            blind_records.append({
                "run_id": run_id,
                "motor_id": f"motor_{motor}",
                "observation_count": len(observations),
                "time_range": {
                    "first": first_metadata.get("source_timestamp"),
                    "last": last_metadata.get("source_timestamp"),
                },
                "motor_temperature_range": {
                    "minimum": min(telemetry_values) if telemetry_values else None,
                    "maximum": max(telemetry_values) if telemetry_values else None,
                },
                "source_metadata": {
                    "source": first_metadata.get("source"),
                    "run_id": first_metadata.get("run_id"),
                    "motor_id": first_metadata.get("motor_id"),
                    "original_file": first_metadata.get("original_file"),
                    "original_columns": deepcopy(first_metadata.get("original_columns") or []),
                    "mapped_fields": ["time_step", "motor_temperature"],
                    "unmapped_source_fields": ["position", "voltage"],
                    "timestamps_preserved_from": "source_metadata.source_timestamp",
                },
                "genesis": {
                    "final_state": (final.get("reliability_state") or {}).get("current"),
                    "lifecycle_state": incident.get("status", "NO_INCIDENT"),
                    "observation_quality": quality,
                    "temporal_patterns": deepcopy(
                        (final.get("evidence_synthesis") or {}).get("pattern_evidence") or []
                    ),
                    "pattern_analysis": deepcopy(
                        (final.get("evidence_synthesis") or {}).get("pattern_analysis") or {}
                    ),
                    "engineering_signals": deepcopy(
                        (final.get("engineering_signals") or {}).get("signals") or []
                    ),
                    "ml_inference": deepcopy(final.get("ml_inference") or {}),
                    "diagnosis": deepcopy((final.get("ml_inference") or {}).get("diagnosis")),
                    "fleet_context": deepcopy(final.get("fleet_context") or {}),
                    "baseline_context": {
                        "visibility": deepcopy(final.get("baseline_visibility") or {}),
                        "historical_comparison": deepcopy(final.get("historical_comparison") or {}),
                    },
                    "historical_memory": deepcopy(final.get("historical_memory") or {}),
                    "evidence_synthesis": deepcopy(final.get("evidence_synthesis") or {}),
                    "recommendation": deepcopy(final.get("recommendation") or {}),
                    "limitations": deepcopy(final.get("limitations") or []),
                    "investigation_report": report,
                    "final_observation_timestamp": last_metadata.get("source_timestamp"),
                },
            })
    return blind_records


def load_post_hoc_ground_truth(dataset_root, blind_records):
    """Load labels/Excel metadata after blind results already exist."""
    workbook = _find_workbook(Path(dataset_root).expanduser())
    metadata = {item["run_id"]: item for item in _read_test_conditions(workbook)}
    post_hoc = []
    for blind in blind_records:
        run_id = blind["run_id"]
        motor_number = int(blind["motor_id"].split("_")[-1])
        adapter = RealRobotDatasetAdapter(dataset_root, run_id, motor_number)
        labels = adapter.load_ground_truth()
        positive = [item for item in labels if _is_positive_label(item.get("label"))]
        run_metadata = metadata.get(run_id, {})
        marked = _is_marked_failure(
            (run_metadata.get("failure_values") or {}).get(str(motor_number))
        )
        first_positive = positive[0]["timestamp"] if positive else None
        last_positive = positive[-1]["timestamp"] if positive else None
        relationship = _relationship(blind["genesis"], positive, marked)
        label_alignment = (
            "MARKED_AND_POSITIVE_LABELS_PRESENT" if marked and positive else
            "MARKED_BUT_NO_POSITIVE_LABELS" if marked else
            "NOT_MARKED_BUT_POSITIVE_LABELS_PRESENT" if positive else
            "NOT_MARKED_AND_NO_POSITIVE_LABELS"
        )
        post_hoc.append({
            "run_id": run_id,
            "motor_id": blind["motor_id"],
            "dataset_metadata": {
                "description": run_metadata.get("description"),
                "documented_failure": marked,
                "label_alignment": label_alignment,
            },
            "positive_label_count": len(positive),
            "first_positive_label_timestamp": first_positive,
            "last_positive_label_timestamp": last_positive,
            "comparison_with_genesis": relationship,
        })
    return post_hoc


def run_blind_experiment(dataset_root, output_path=None,
                         failure_run_id=FAILURE_RUN_ID,
                         comparison_run_id=COMPARISON_RUN_ID):
    """Produce blind results first, then append the separate post-hoc section."""
    blind_records = build_blind_genesis_results(
        dataset_root, (failure_run_id, comparison_run_id)
    )
    post_hoc = load_post_hoc_ground_truth(dataset_root, blind_records)
    result = {
        "experiment": "GENESIS EXTERNAL DATA EXPERIMENT #1",
        "sections": {
            "blind_genesis_results": {
                "records": blind_records,
                "ground_truth_loaded": False,
                "inputs_to_genesis": ["time_step", "motor_temperature", "robot/run identity", "source metadata"],
                "excluded_from_genesis": ["label values", "Test conditions.xlsx failure metadata", "position", "voltage"],
            },
            "post_hoc_ground_truth": {
                "loaded_after_blind_results": True,
                "records": post_hoc,
            },
        },
        "interpretation_limits": [
            "This is a descriptive comparison, not an accuracy estimate.",
            "Only source time and motor temperature entered Genesis; position and voltage were not mapped into the canonical telemetry contract.",
            "No fitted ML or diagnosis artifact is configured in the existing Genesis facade used here.",
            "Ground-truth labels and workbook flags were read only after all Genesis results were produced.",
        ],
    }
    if output_path is not None:
        output = Path(output_path).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    return result


def _relationship(genesis, positive_labels, documented_failure):
    patterns = genesis.get("temporal_patterns") or []
    signals = genesis.get("engineering_signals") or []
    has_signal = bool(patterns or signals)
    if not positive_labels:
        if documented_failure:
            category = "GENESIS_SIGNAL_WITH_METADATA_FAILURE_BUT_NO_POSITIVE_LABELS" if has_signal else "GROUND_TRUTH_METADATA_WITHOUT_POSITIVE_LABELS"
        else:
            category = "GENESIS_SIGNAL_WITHOUT_GROUND_TRUTH_FAILURE" if has_signal else "NO_GROUND_TRUTH_FAILURE_INDICATED"
        return {"category": category, "genesis_signal_present_in_final_result": has_signal,
                "disagreement": False,
                "metadata_label_inconsistency": bool(documented_failure)}

    if not has_signal:
        quality = genesis.get("observation_quality") or {}
        limited = quality.get("status") != "AVAILABLE" or quality.get("prediction_ready") is False
        category = "INSUFFICIENT_EVIDENCE" if limited else "NO_GENESIS_SIGNAL"
        return {"category": category, "genesis_signal_present_in_final_result": False,
                "disagreement": not limited,
                "possible_output_gap": True,
                "reason": "Genesis emitted no temporal pattern or engineering signal in the final result."}

    # A batch investigation exposes its final evidence, not the first sample
    # at which a signal appeared. Avoid making an unsupported timing claim.
    return {
        "category": "FINAL_RESULT_HAS_SIGNAL_TIMING_UNAVAILABLE",
        "genesis_signal_present_in_final_result": True,
        "first_positive_label_timestamp": positive_labels[0].get("timestamp"),
        "last_positive_label_timestamp": positive_labels[-1].get("timestamp"),
        "disagreement": False,
        "reason": "Genesis batch output does not expose first-signal timing; this result is not a timing comparison.",
    }


def _is_positive_label(value):
    try:
        return float(value) == 1.0
    except (TypeError, ValueError):
        return False


def render_summary(result):
    sections = result["sections"]
    blind_by_key = {
        (record["run_id"], record["motor_id"]): record
        for record in sections["blind_genesis_results"]["records"]
    }
    posthoc_by_key = {
        (record["run_id"], record["motor_id"]): record
        for record in sections["post_hoc_ground_truth"]["records"]
    }
    lines = ["GENESIS EXTERNAL DATA EXPERIMENT #1", ""]
    runs = list(dict.fromkeys(record["run_id"] for record in sections["blind_genesis_results"]["records"]))
    for run_index, run_id in enumerate(runs):
        lines.extend([f"BLIND RUN {'A' if run_index == 0 else 'B'}", f"Run: {run_id}"])
        for motor in MOTORS:
            key = (run_id, f"motor_{motor}")
            blind = blind_by_key[key]
            gt = posthoc_by_key[key]
            genesis = blind["genesis"]
            patterns = [item.get("supporting_data", {}).get("pattern") for item in genesis["temporal_patterns"]]
            signals = [item.get("signal") for item in genesis["engineering_signals"]]
            lines.extend([
                f"\nMotor: {blind['motor_id']}",
                "Genesis observed: "
                f"{blind['observation_count']} samples; motor temperature "
                f"{blind['motor_temperature_range']['minimum']} → {blind['motor_temperature_range']['maximum']}",
                "Genesis detected: " + (", ".join(str(value) for value in patterns + signals if value) or "no temporal pattern or engineering signal in the final result"),
                f"Genesis state: {genesis['final_state']} (lifecycle: {genesis['lifecycle_state']})",
                "Recommendation: " + str(genesis["recommendation"].get("recommendation") or "Unavailable"),
                "Ground truth revealed AFTER blind analysis: "
                + ("documented failure" if gt["dataset_metadata"]["documented_failure"] else "no failure marked")
                + f"; positive labels={gt['positive_label_count']}",
                "Relationship: " + gt["comparison_with_genesis"]["category"],
            ])

    blind_records = sections["blind_genesis_results"]["records"]
    posthoc_records = sections["post_hoc_ground_truth"]["records"]
    lines.extend(["", "WHAT GENESIS ACTUALLY SAW"])
    lines.append("- Source timestamps and motor_temperature only, plus run/motor identity and provenance metadata.")
    lines.append("- It did not receive labels, workbook failure flags, position, or voltage.")
    lines.extend(["", "WHAT GENESIS DID NOT HAVE"])
    lines.extend("- " + item for item in result["interpretation_limits"])
    lines.extend(["", "WHAT GROUND TRUTH REVEALED"])
    lines.append(f"- {sum(item['positive_label_count'] for item in posthoc_records)} positive labels across the 12 tested run/motors.")
    lines.append(f"- {sum(item['dataset_metadata']['documented_failure'] for item in posthoc_records)} tested motor/run pairs marked as failure.")
    lines.extend(["", "IMPORTANT DISAGREEMENTS"])
    disagreements = [item for item in posthoc_records if item["comparison_with_genesis"].get("disagreement")]
    lines.append("- None by the experiment's descriptive timing categories." if not disagreements else
                 "- " + ", ".join(f"{item['run_id']}/{item['motor_id']}: {item['comparison_with_genesis']['category']}" for item in disagreements))
    lines.extend(["", "ARCHITECTURAL LIMITATIONS"])
    lines.append("- Dataset position/voltage have no established canonical mapping in this experiment; their values were excluded from Genesis telemetry.")
    lines.append("- No model result is available unless an existing fitted artifact is configured.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--output", default="real-data-blind-test.json")
    parser.add_argument("--comparison-run", default=COMPARISON_RUN_ID)
    args = parser.parse_args(argv)
    result = run_blind_experiment(
        args.dataset_root, args.output, comparison_run_id=args.comparison_run
    )
    print(render_summary(result))
    print(f"\nJSON report: {Path(args.output).expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
