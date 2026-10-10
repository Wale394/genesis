
"""
GENESIS Behavioral Baseline Prototype v0.2

Research-only.
This version deliberately focuses on behavioral change rather than sensor spikes.

Candidate evidence:
    SUSTAINED_CONTEXTUAL_DRIFT

Requirements:
    - temperature changes persist over a long window
    - net temperature change is meaningful
    - operating context (position) remains relatively stable
    - labels are never read

No failure/health classification is produced.
"""

from __future__ import annotations
import argparse
import csv
import json
import math
import statistics
from pathlib import Path


def load_rows(path):
    rows = []
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"time", "position", "temperature", "voltage"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
        for r in reader:
            # label is intentionally ignored
            rows.append({
                "time": float(r["time"]),
                "position": float(r["position"]),
                "temperature": float(r["temperature"]),
                "voltage": float(r["voltage"]),
            })
    return rows


def linear_slope(values):
    n = len(values)
    if n < 2:
        return None
    x_mean = (n - 1) / 2
    y_mean = statistics.fmean(values)
    denom = sum((i - x_mean) ** 2 for i in range(n))
    if denom == 0:
        return 0.0
    return sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values)) / denom


def analyze(rows, window=300, min_temp_change=5.0,
            min_slope_per_sample=0.015, max_position_range=5.0):
    out = []

    temps = []
    positions = []

    for i, row in enumerate(rows):
        temps.append(row["temperature"])
        positions.append(row["position"])

        if i + 1 < window:
            out.append({
                **row,
                "window_ready": False,
                "evidence": []
            })
            continue

        t = temps[i - window + 1:i + 1]
        p = positions[i - window + 1:i + 1]

        slope = linear_slope(t)
        net_change = t[-1] - t[0]
        position_range = max(p) - min(p)

        evidence = []

        # Deliberately require all three conditions.
        if (
            slope is not None
            and slope >= min_slope_per_sample
            and net_change >= min_temp_change
            and position_range <= max_position_range
        ):
            evidence.append("SUSTAINED_CONTEXTUAL_THERMAL_DRIFT")

        out.append({
            **row,
            "window_ready": True,
            "window_observations": window,
            "temperature_slope_per_sample": slope,
            "temperature_net_change": net_change,
            "position_range": position_range,
            "evidence": evidence,
        })

    return out


def summarize(results):
    hits = [r for r in results if "SUSTAINED_CONTEXTUAL_THERMAL_DRIFT" in r["evidence"]]
    if not hits:
        return {
            "observations": len(results),
            "drift_hits": 0,
            "first_hit": None,
            "last_hit": None,
            "max_net_temperature_change": max(
                (r.get("temperature_net_change", float("-inf")) for r in results),
                default=None,
            ),
        }

    return {
        "observations": len(results),
        "drift_hits": len(hits),
        "first_hit": {
            "time": hits[0]["time"],
            "temperature": hits[0]["temperature"],
            "position": hits[0]["position"],
            "net_temperature_change": hits[0]["temperature_net_change"],
            "position_range": hits[0]["position_range"],
        },
        "last_hit": {
            "time": hits[-1]["time"],
            "temperature": hits[-1]["temperature"],
            "position": hits[-1]["position"],
            "net_temperature_change": hits[-1]["temperature_net_change"],
            "position_range": hits[-1]["position_range"],
        },
        "max_net_temperature_change": max(
            r.get("temperature_net_change", float("-inf")) for r in results
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output")
    args = ap.parse_args()

    results = analyze(load_rows(args.input))
    report = {
        "prototype": "GENESIS Behavioral Baseline Prototype v0.2",
        "ground_truth_used": False,
        "summary": summarize(results),
        "limitations": [
            "This is not integrated into Genesis.",
            "Thresholds are experimental parameters, not production reliability thresholds.",
            "Position is used only as an operating-context proxy.",
            "Voltage is preserved but not interpreted.",
            "The method does not infer failure or causation.",
            "A single run is not sufficient to establish a behavioral baseline.",
        ],
    }

    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
