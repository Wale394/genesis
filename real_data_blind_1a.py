"""Single-motor, blind full-history Genesis replay for external dataset 1A."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
from time import perf_counter, time
import sys

from genesis import Genesis
from investigation_report import build_investigation_report
from real_robot_dataset_adapter import RealRobotDatasetAdapter
from real_data_semantic_report import _find_workbook, _is_marked_failure, _read_test_conditions


RUN_ID = "20240325_155003"
MOTOR = 1
MAX_RUNTIME_SECONDS = 600


class ReplayTimeout(RuntimeError):
    def __init__(self, processed, elapsed, peak_bytes):
        super().__init__("Single-motor Genesis replay exceeded its 10-minute limit")
        self.processed = processed
        self.elapsed = elapsed
        self.peak_bytes = peak_bytes


def _write_json(path, payload):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _blind_result(dataset_root):
    adapter = RealRobotDatasetAdapter(dataset_root, RUN_ID, MOTOR)
    observations = adapter.load_observations()
    if len(observations) != 6652:
        raise ValueError(f"Expected 6,652 observations, found {len(observations)}")
    # Enforce the adapter boundary before any Genesis call.
    for observation in observations:
        if set(observation.get("telemetry", {})) != {"time_step", "motor_temperature"}:
            raise ValueError("Adapter returned fields outside the approved blind telemetry input")
        if "label" in observation or "failure_event" in observation or "failure_type" in observation:
            raise ValueError("Ground-truth/failure fields must not enter Genesis observations")

    genesis = Genesis()
    started = perf_counter()
    progress = {"processed": 0, "last_report": 0, "peak_bytes": None}
    pipeline = genesis._pipeline
    original_evaluate = pipeline.evaluate
    try:
        import psutil
        process = psutil.Process()
    except ImportError:
        process = None

    def tracked_evaluate(*args, **kwargs):
        elapsed = perf_counter() - started
        if elapsed >= MAX_RUNTIME_SECONDS:
            raise ReplayTimeout(progress["processed"], elapsed, progress["peak_bytes"])
        result = original_evaluate(*args, **kwargs)
        progress["processed"] += 1
        if process is not None and progress["processed"] % 100 == 0:
            current_bytes = process.memory_info().rss
            progress["peak_bytes"] = max(progress["peak_bytes"] or 0, current_bytes)
        if progress["processed"] % 250 == 0 or elapsed - progress["last_report"] >= 30:
            print(f"progress observations={progress['processed']}/{len(observations)} elapsed_seconds={elapsed:.1f}", flush=True)
            progress["last_report"] = elapsed
        return result

    pipeline.evaluate = tracked_evaluate
    final = genesis.investigate(observations)
    processing_seconds = perf_counter() - started
    report = build_investigation_report(final)
    metadata = observations[0]["source_metadata"]
    final_metadata = observations[-1]["source_metadata"]
    quality = deepcopy(final.get("observation_quality") or {})
    incident = deepcopy(final.get("incident") or {})
    evidence = deepcopy(final.get("evidence_synthesis") or {})
    signals = deepcopy((final.get("engineering_signals") or {}).get("signals") or [])
    patterns = deepcopy(evidence.get("pattern_evidence") or [])
    for signal in signals:
        signal.setdefault("observed_at_timestamp", final_metadata.get("source_timestamp"))

    return {
        "experiment": "GENESIS EXTERNAL DATA EXPERIMENT #1A",
        "blind_results": {
            "run": {
                "run_id": RUN_ID,
                "motor_id": f"motor_{MOTOR}",
                "observation_count": len(observations),
                "observations_successfully_analyzed": final.get("processing", {}).get("observation_count", len(observations)),
                "first_timestamp": metadata.get("source_timestamp"),
                "final_timestamp": final_metadata.get("source_timestamp"),
                "source": metadata.get("source"),
                "original_file": metadata.get("original_file"),
                "original_columns": deepcopy(metadata.get("original_columns") or []),
                "genesis_fields": ["time_step", "motor_temperature", "robot/motor identity", "source/provenance metadata"],
                "unmapped_fields": ["position", "voltage", "label"],
            },
            "performance": {
                "genesis_processing_seconds": round(processing_seconds, 3),
                "completed": True,
                "observations_processed": len(observations),
                "observations_successfully_analyzed": final.get("processing", {}).get("observation_count", len(observations)),
                "memory_note": "Peak process memory was not sampled by the Genesis API runner.",
                "peak_memory_bytes_approx": progress["peak_bytes"],
            },
            "observation_quality": {
                "state": quality.get("status"),
                "findings": deepcopy(quality.get("findings") or []),
                "limitations": deepcopy(quality.get("limitations") or []),
                "full_result": quality,
            },
            "temporal_analysis": {
                "patterns_detected_in_final_result": patterns,
                "pattern_analysis": deepcopy(evidence.get("pattern_analysis") or {}),
                "timing_note": "Pattern evidence is the final batch result; Genesis does not expose first-detection timestamps in this API result.",
            },
            "engineering_signals": {
                "signals_in_final_result": signals,
                "evaluated_at_timestamp": final_metadata.get("source_timestamp"),
                "timing_note": "Signals are from the final observation evaluation; no first-detection timing is exposed by the batch API.",
            },
            "ml": deepcopy(final.get("ml_inference") or {}),
            "diagnosis": deepcopy((final.get("ml_inference") or {}).get("diagnosis")),
            "fleet_baseline": {
                "fleet_context": deepcopy(final.get("fleet_context") or {}),
                "baseline_visibility": deepcopy(final.get("baseline_visibility") or {}),
                "historical_comparison": deepcopy(final.get("historical_comparison") or {}),
            },
            "historical_memory": deepcopy(final.get("historical_memory") or {}),
            "evidence_synthesis": {
                "observations": deepcopy(evidence.get("observation_evidence") or evidence.get("observations") or []),
                "patterns": deepcopy(evidence.get("pattern_evidence") or []),
                "engineering": deepcopy(evidence.get("engineering_evidence") or []),
                "ml": deepcopy(evidence.get("ml_evidence") or []),
                "limitations": deepcopy(evidence.get("limitations") or []),
                "tensions": deepcopy(evidence.get("tensions") or evidence.get("contradictions") or []),
                "full_result": evidence,
            },
            "state_lifecycle": {
                "final_state": (final.get("reliability_state") or {}).get("current"),
                "lifecycle_state": incident.get("status", "NO_INCIDENT"),
                "transitions": deepcopy((final.get("processing") or {}).get("state_transitions") or []),
                "full_incident": incident,
            },
            "recommendation": deepcopy(final.get("recommendation") or {}),
            "limitations": deepcopy(final.get("limitations") or []),
            "investigation_report": report,
        },
    }


def _post_hoc(dataset_root, blind):
    run = blind["blind_results"]["run"]
    labels = RealRobotDatasetAdapter(dataset_root, RUN_ID, MOTOR).load_ground_truth()
    positive = [record for record in labels if _positive(record.get("label"))]
    workbook = _find_workbook(Path(dataset_root).expanduser())
    conditions = {record["run_id"]: record for record in _read_test_conditions(workbook)}
    metadata = conditions.get(RUN_ID, {})
    marked = _is_marked_failure((metadata.get("failure_values") or {}).get(str(MOTOR)))
    genesis = blind["blind_results"]
    signals = genesis["engineering_signals"]["signals_in_final_result"]
    patterns = genesis["temporal_analysis"]["patterns_detected_in_final_result"]
    has_signal = bool(signals or patterns)
    first_label = positive[0].get("timestamp") if positive else None
    final_timestamp = run["final_timestamp"]
    if not positive:
        category = "GROUND_TRUTH_NOT_OBSERVABLE"
    elif not has_signal:
        category = "INSUFFICIENT_EVIDENCE" if genesis["observation_quality"]["state"] != "AVAILABLE" else "NO_GENESIS_SIGNAL"
    else:
        try:
            if float(final_timestamp) < float(first_label):
                category = "GENESIS_SIGNAL_BEFORE_LABEL"
            elif float(final_timestamp) == float(first_label):
                category = "GENESIS_SIGNAL_MATCH"
            else:
                category = "GENESIS_SIGNAL_AFTER_LABEL"
        except (TypeError, ValueError):
            category = "GROUND_TRUTH_NOT_OBSERVABLE"
    return {
        "documented_failure_status": marked,
        "positive_label_count": len(positive),
        "first_positive_label_timestamp": first_label,
        "last_positive_label_timestamp": positive[-1].get("timestamp") if positive else None,
        "genesis_signal_detected_in_final_result": has_signal,
        "signal_timing_classification": category,
        "timing_caveat": "The classification compares the final batch-evaluation timestamp with the first positive label. It does not establish when a signal first emerged during the stream.",
        "notable_disagreements": [] if has_signal == bool(positive) else ["Final Genesis signal presence differs from whether positive labels exist."],
        "evidence_limitations": genesis["limitations"],
    }


def _positive(value):
    try:
        return float(value) == 1.0
    except (TypeError, ValueError):
        return False


def run(dataset_root, json_path="real-data-blind-1a.json", text_path="real-data-blind-1a.txt"):
    # Strict two-phase order: persist blind-only outputs before opening labels/XLSX.
    result = _blind_result(dataset_root)
    _write_json(json_path, result)
    run_record = result["blind_results"]["run"]
    text = [
        "GENESIS EXTERNAL DATA EXPERIMENT #1A — BLIND RESULT",
        f"Run/motor: {RUN_ID}/motor_{MOTOR}",
        f"Observations: {run_record['observation_count']} processed; {result['blind_results']['performance']['observations_successfully_analyzed']} analyzed",
        f"Time: {run_record['first_timestamp']} → {run_record['final_timestamp']}",
        f"Genesis final state: {result['blind_results']['state_lifecycle']['final_state']}",
        f"Quality: {result['blind_results']['observation_quality']['state']}",
        f"Patterns: {len(result['blind_results']['temporal_analysis']['patterns_detected_in_final_result'])}",
        f"Engineering signals: {len(result['blind_results']['engineering_signals']['signals_in_final_result'])}",
        f"ML available: {result['blind_results']['ml'].get('prediction_available', False)}",
        f"Genesis processing seconds: {result['blind_results']['performance']['genesis_processing_seconds']}",
        "Ground truth not loaded in this initial blind text.",
    ]
    Path(text_path).expanduser().write_text("\n".join(text) + "\n", encoding="utf-8")

    post_hoc = _post_hoc(dataset_root, result)
    result["post_hoc_validation"] = post_hoc
    _write_json(json_path, result)
    text.extend(["", "POST-HOC VALIDATION", f"Documented failure: {post_hoc['documented_failure_status']}",
                 f"Positive labels: {post_hoc['positive_label_count']}",
                 f"First positive label: {post_hoc['first_positive_label_timestamp']}",
                 f"Final-result comparison: {post_hoc['signal_timing_classification']}",
                 post_hoc["timing_caveat"]])
    Path(text_path).expanduser().write_text("\n".join(text) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--json", default="real-data-blind-1a.json")
    parser.add_argument("--text", default="real-data-blind-1a.txt")
    args = parser.parse_args()
    try:
        result = run(args.dataset_root, args.json, args.text)
    except ReplayTimeout as timeout:
        memory_mb = round(timeout.peak_bytes / (1024 * 1024), 1) if timeout.peak_bytes else "unavailable"
        print("REPLAY STOPPED AT TIME LIMIT", flush=True)
        print(f"observations_successfully_analyzed={timeout.processed}/6652", flush=True)
        print(f"elapsed_seconds={timeout.elapsed:.1f}", flush=True)
        print(f"peak_process_memory_mb_approx={memory_mb}", flush=True)
        print("stage=Genesis.investigate chronological replay; no partial Genesis conclusion or ground-truth read", flush=True)
        return 2
    print(Path(args.text).read_text(encoding="utf-8"))
    print(f"JSON report: {Path(args.json).resolve()}")
    return result


if __name__ == "__main__":
    main()
