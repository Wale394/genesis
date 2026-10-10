
"""
GENESIS Behavioral Baseline Prototype v0.1

Research-only prototype.
- Uses telemetry only.
- The dataset label column is ignored.
- Does not make failure/health decisions.
- Does not modify Genesis production code.

Core idea:
    current behavior
        vs
    behavior observed recently in the same context
        ->
    contextual behavioral change evidence

Context v0.1:
    position bucket

Signals:
    temperature residual from prior contextual baseline
    robust deviation (MAD-based)
    temperature change over a configurable window
    persistence of elevated deviation

This is intentionally simple. It is an experiment, not a production Genesis component.
"""

from __future__ import annotations
import argparse
import csv
import json
import math
import statistics
from collections import defaultdict, deque
from pathlib import Path


def median(values):
    values = [v for v in values if math.isfinite(v)]
    return statistics.median(values) if values else None


def mad(values, center):
    values = [abs(v - center) for v in values if math.isfinite(v)]
    return statistics.median(values) if values else None


def load_telemetry_csv(path):
    rows = []
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"time", "position", "temperature", "voltage"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required telemetry columns: {sorted(missing)}")

        for row in reader:
            # IMPORTANT: label is intentionally never read.
            rows.append({
                "time": float(row["time"]),
                "position": float(row["position"]),
                "temperature": float(row["temperature"]),
                "voltage": float(row["voltage"]),
            })
    return rows


def analyze(rows, position_bucket=25, history_window=100, elevated_z=3.0):
    """
    Online analysis:
    each observation is compared only with prior observations.

    This avoids using future data and keeps the prototype compatible
    with a future streaming Genesis architecture.
    """
    contexts = defaultdict(lambda: deque(maxlen=history_window))
    previous_temperatures = deque(maxlen=history_window)
    elevated_history = deque(maxlen=history_window)

    results = []

    for row in rows:
        context = int(math.floor(row["position"] / position_bucket) * position_bucket)
        history = contexts[context]

        baseline = median([item["temperature"] for item in history])
        scale = None
        z = None

        if baseline is not None and len(history) >= history_window:
            deviations = [abs(item["temperature"] - baseline) for item in history]
            m = statistics.median(deviations)
            scale = max(1.4826 * m, 1.0)
            z = (row["temperature"] - baseline) / scale

        temp_change = None
        if len(previous_temperatures) >= history_window:
            temp_change = row["temperature"] - previous_temperatures[0]

        elevated = bool(z is not None and z >= elevated_z)
        elevated_history.append(1 if elevated else 0)

        persistence = (
            sum(elevated_history) / len(elevated_history)
            if elevated_history else 0.0
        )

        evidence = []
        if z is not None and z >= elevated_z:
            evidence.append("CONTEXTUAL_TEMPERATURE_DEVIATION")
        if temp_change is not None and abs(temp_change) >= 5:
            evidence.append("SUSTAINED_TEMPERATURE_CHANGE")
        if persistence >= 0.30:
            evidence.append("PERSISTENT_CONTEXTUAL_CHANGE")

        results.append({
            "time": row["time"],
            "position": row["position"],
            "temperature": row["temperature"],
            "voltage": row["voltage"],
            "context": context,
            "context_history_count": len(history),
            "context_temperature_baseline": baseline,
            "context_scale": scale,
            "context_temperature_z": z,
            "temperature_change_over_window": temp_change,
            "elevated_persistence": persistence,
            "evidence": evidence,
        })

        history.append(row)
        previous_temperatures.append(row["temperature"])

    return results


def summarize(results):
    evidence_counts = defaultdict(int)
    for r in results:
        for e in r["evidence"]:
            evidence_counts[e] += 1

    strongest = sorted(
        [r for r in results if r["evidence"]],
        key=lambda r: (
            len(r["evidence"]),
            r["elevated_persistence"],
            abs(r["context_temperature_z"] or 0),
        ),
        reverse=True,
    )[:20]

    return {
        "observations": len(results),
        "evidence_counts": dict(evidence_counts),
        "strongest_evidence_points": strongest,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    rows = load_telemetry_csv(args.input)
    results = analyze(rows)
    report = {
        "prototype": "GENESIS Behavioral Baseline Prototype v0.1",
        "ground_truth_used": False,
        "input": str(args.input),
        "summary": summarize(results),
        "limitations": [
            "Position is used only as an experimental context bucket.",
            "Voltage is preserved but not interpreted.",
            "The label column is never read.",
            "This prototype does not infer failure or causation.",
            "The baseline can be contaminated by earlier abnormal behavior.",
            "The prototype is not integrated into Genesis production logic.",
        ],
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
