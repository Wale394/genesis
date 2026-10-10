"""Optional expected sampling cadence and factual timestamp-interval analysis.

This module describes timestamp evidence only. A possible gap is not proof that
an observation was lost, nor evidence of a sensor or robot failure.
"""

import math
from collections.abc import Mapping
from numbers import Real


def validate_sampling_context(value):
    """Return a normalized context, or ``None`` when cadence is unspecified."""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("sampling_context must be an object or null")
    unknown = set(value) - {"expected_interval", "allowed_jitter"}
    if unknown:
        raise ValueError("unsupported sampling_context field(s): " + ", ".join(sorted(unknown)))
    if "expected_interval" not in value or "allowed_jitter" not in value:
        raise ValueError("sampling_context requires expected_interval and allowed_jitter")
    expected = _finite_number(value["expected_interval"], "expected_interval")
    jitter = _finite_number(value["allowed_jitter"], "allowed_jitter")
    if expected <= 0:
        raise ValueError("expected_interval must be greater than zero")
    if jitter < 0:
        raise ValueError("allowed_jitter must be zero or greater")
    return {"expected_interval": expected, "allowed_jitter": jitter}


def _finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def analyze_sampling_intervals(time_steps, sampling_context=None):
    """Describe adjacent existing ``time_step`` values without inventing data."""
    context = validate_sampling_context(sampling_context)
    raw_steps = list(time_steps or ())
    steps = [
        None if value is None else _finite_number(value, "time_step")
        for value in raw_steps
    ]
    present = [value for value in steps if value is not None]
    if any(current <= previous for previous, current in zip(present, present[1:])):
        raise ValueError("time_steps must be strictly increasing")

    intervals = []
    for previous, current in zip(steps, steps[1:]):
        # A synthetic ingestion-order step or absent source timestamp cannot
        # support an elapsed-time calculation. Do not bridge across it.
        if previous is None or current is None:
            continue
        observed = round(current - previous, 9)
        item = {
            "previous_time_step": _json_number(previous),
            "current_time_step": _json_number(current),
            "observed_interval": observed,
        }
        if context is None:
            item.update({
                "classification": "TIMESTAMP_INTERVAL_OBSERVED",
                "sampling_context": "UNSPECIFIED",
                "description": (
                    f"Observed timestamp interval {observed}; expected sampling "
                    "interval is unspecified."
                ),
            })
        else:
            expected = context["expected_interval"]
            jitter = context["allowed_jitter"]
            item.update({
                "sampling_context": "CONFIGURED",
                "expected_interval": expected,
                "allowed_jitter": jitter,
            })
            difference = abs(observed - expected)
            if difference <= jitter:
                item["classification"] = "NORMAL_INTERVAL"
                item["description"] = "Observed timestamp interval is within the configured sampling tolerance."
            elif observed > expected + jitter:
                item["classification"] = "POSSIBLE_DATA_GAP"
                item["excess_interval"] = round(observed - expected - jitter, 9)
                item["description"] = (
                    "Observed timestamp interval exceeds the configured expected "
                    "sampling interval; possible telemetry gap, not proof of lost observations."
                )
            else:
                item["classification"] = "SHORTER_THAN_EXPECTED"
                item["description"] = (
                    "Observed timestamp interval is shorter than the configured "
                    "expected sampling interval beyond allowed jitter."
                )
        intervals.append(item)

    possible_gaps = [item for item in intervals if item["classification"] == "POSSIBLE_DATA_GAP"]
    limitations = []
    if len(intervals) == 0 and len(steps) > 1:
        limitations.append("No adjacent pair of source timestamps is available for interval analysis.")
    if context is None and len(intervals) > 0:
        limitations.append(
            "Sampling cadence is unspecified; observed timestamp intervals cannot be classified as missing telemetry."
        )
    if possible_gaps:
        limitations.append("A possible data gap does not establish that observations were lost.")
    if any(value is None for value in steps):
        limitations.append(
            "One or more source timestamps were unavailable; interval analysis does not bridge those observations."
        )
    return {
        "status": "UNKNOWN" if context is None else "CONFIGURED",
        "sampling_context": context,
        "timestamp_count": len(steps),
        "source_timestamp_count": len(present),
        "interval_count": len(intervals),
        "intervals": intervals,
        "possible_gap_count": len(possible_gaps),
        "limitations": limitations,
    }


def _json_number(value):
    return int(value) if value.is_integer() else value
