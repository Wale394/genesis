"""Descriptive quality and evidence summary for offline telemetry reports.

This module summarizes values already present in a recorded session. It does not
classify failures, infer causes, or decide whether a value is anomalous.
"""
from collections import Counter
from statistics import median


def build_offline_data_review(session):
    if not isinstance(session, dict):
        raise ValueError("field session must be an object")
    observations = session.get("observations") or []
    context = session.get("field_test_context") or {}
    if not observations:
        raise ValueError("field session contains no observations")

    mapped = context.get("mapped_fields") or {}
    signals = {}
    total_expected = len(observations) * len(mapped)
    total_present = 0
    for source_field, mapping in mapped.items():
        target = mapping.get("target") if isinstance(mapping, dict) else None
        if not target:
            continue
        values = []
        missing = 0
        for observation in observations:
            telemetry = observation.get("telemetry") or {}
            value = telemetry.get(target)
            if value is None:
                missing += 1
            else:
                total_present += 1
                values.append(value)
        item = {
            "source_field": source_field,
            "target": target,
            "source_unit": mapping.get("source_unit") if isinstance(mapping, dict) else None,
            "canonical_unit": mapping.get("canonical_unit") if isinstance(mapping, dict) else None,
            "record_count": len(observations),
            "present_count": len(values),
            "missing_count": missing,
            "completeness_percent": round((len(values) / len(observations)) * 100, 2),
        }
        if target == "robot_state":
            item["value_counts"] = dict(Counter(str(value) for value in values))
        else:
            numeric = [float(value) for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
            if numeric:
                item.update({
                    "first_value": numeric[0],
                    "last_value": numeric[-1],
                    "minimum": min(numeric),
                    "maximum": max(numeric),
                    "mean": round(sum(numeric) / len(numeric), 6),
                    "median": median(numeric),
                    "net_change": round(numeric[-1] - numeric[0], 6),
                })
        signals[target] = item

    timestamps = []
    for observation in observations:
        value = (observation.get("telemetry") or {}).get("time_step")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            timestamps.append(float(value))
    gaps = [right - left for left, right in zip(timestamps, timestamps[1:]) if right > left]
    time_review = {
        "timestamp_count": len(timestamps),
        "strictly_increasing": len(timestamps) == len(observations) and all(b > a for a, b in zip(timestamps, timestamps[1:])),
        "first_timestamp_seconds": timestamps[0] if timestamps else None,
        "last_timestamp_seconds": timestamps[-1] if timestamps else None,
        "interval_count": len(gaps),
        "minimum_interval_seconds": min(gaps) if gaps else None,
        "median_interval_seconds": median(gaps) if gaps else None,
        "maximum_interval_seconds": max(gaps) if gaps else None,
    }
    expected = total_expected if mapped else 0
    return {
        "review_type": "DESCRIPTIVE_OFFLINE_TELEMETRY_REVIEW",
        "record_count": len(observations),
        "mapped_signal_count": len(signals),
        "mapped_reading_completeness_percent": round((total_present / expected) * 100, 2) if expected else None,
        "signals": signals,
        "time_review": time_review,
        "interpretation_boundary": {
            "observed_patterns_are_not_confirmed_failures": True,
            "failure_prediction_is_not_validated_by_this_report": True,
            "cause_is_not_established_by_descriptive_statistics": True,
        },
        "limitations": [
            "Statistics describe only the mapped values in this recorded file.",
            "No engineering limits or failure thresholds were applied by this summary.",
            "Source identity, sensor calibration, and declared units were not independently authenticated.",
            "A change or extreme value is a review lead, not proof of a physical failure or its cause.",
            "Failure-prediction accuracy has not been validated by this report.",
        ],
        "recommended_review_steps": [
            "Confirm the asset identity, sensor channel, calibration, and units against source documentation.",
            "Compare reported values with manufacturer limits and the asset's known operating envelope.",
            "Check whether operating mode, workload, ambient conditions, or maintenance events explain changes.",
            "Seek independent inspection or corroborating evidence before recording a physical failure or cause.",
        ],
    }


def render_offline_data_review(review):
    lines = [
        "\nOFFLINE DATA REVIEW — DESCRIPTIVE, NOT A FAILURE DIAGNOSIS",
        f"Records: {review.get('record_count', 0)}",
        f"Mapped signals: {review.get('mapped_signal_count', 0)}",
        f"Mapped reading completeness: {review.get('mapped_reading_completeness_percent')}%" if review.get("mapped_reading_completeness_percent") is not None else "Mapped reading completeness: unavailable",
        "",
        "SIGNAL SUMMARIES",
    ]
    for target, item in (review.get("signals") or {}).items():
        unit = item.get("canonical_unit") or ""
        lines.append(f"- {target} (source: {item.get('source_field')}): {item.get('present_count')}/{item.get('record_count')} present; {item.get('missing_count')} missing; completeness {item.get('completeness_percent')}%")
        if "minimum" in item:
            lines.append(f"  Range: {item['minimum']} to {item['maximum']} {unit}; first {item['first_value']}; last {item['last_value']}; net change {item['net_change']} {unit}; mean {item['mean']}; median {item['median']}")
        elif "value_counts" in item:
            lines.append(f"  State counts: {item['value_counts']}")
    time = review.get("time_review") or {}
    lines.extend([
        "",
        "TIMESTAMP REVIEW",
        f"Strictly increasing timestamps: {time.get('strictly_increasing')}",
        f"Interval count: {time.get('interval_count')}",
        f"Interval seconds (min / median / max): {time.get('minimum_interval_seconds')} / {time.get('median_interval_seconds')} / {time.get('maximum_interval_seconds')}",
        "",
        "INTERPRETATION BOUNDARY",
        "- These are descriptive summaries, not a failure classification or validated prediction.",
        "- Extreme values or changes are review leads; this summary does not establish cause.",
        "- No engineering thresholds were applied here.",
        "",
        "RECOMMENDED ENGINEER REVIEW",
    ])
    lines.extend(f"- {step}" for step in review.get("recommended_review_steps", []))
    lines.extend(["", "LIMITATIONS"])
    lines.extend(f"- {item}" for item in review.get("limitations", []))
    return "\n".join(lines)
