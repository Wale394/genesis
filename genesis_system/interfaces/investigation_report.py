"""Deterministic human-readable projection of existing Genesis evidence.

This module formats existing results only. It does not run inference, score
evidence, change recommendations, or claim causes.
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys


FLEET_LIMITATION = "Fleet comparison is contextual evidence and is not proof of failure."


def build_investigation_report(result):
    """Project one public Genesis result into an engineer-readable report."""
    if not isinstance(result, dict):
        raise ValueError("Genesis investigation result must be an object")

    synthesis = result.get("evidence_synthesis") or {}
    summary = synthesis.get("summary") or {}
    robot = deepcopy(result.get("robot") or {})
    incident = deepcopy(result.get("incident") or {})
    state = (result.get("reliability_state") or {}).get("current")
    ml = deepcopy(result.get("ml_inference") or {})
    memory = deepcopy(result.get("historical_memory") or {})
    historical_comparison = deepcopy(
        result.get("historical_comparison")
        or synthesis.get("historical_comparison") or {}
    )
    fleet = deepcopy(result.get("fleet_context") or {})
    recommendation = result.get("recommendation") or {}
    action = deepcopy(result.get("human_action") or {"status": "PENDING", "items": []})
    outcome = deepcopy(result.get("outcome") or {"status": "OUTCOME_PENDING"})

    what_happened = []
    for item in synthesis.get("observations") or []:
        what_happened.append(_evidence_item(item))
    trajectory = _motor_temperature_trajectory(result.get("processing") or {})
    if trajectory:
        what_happened.insert(0, trajectory)

    patterns = deepcopy(synthesis.get("pattern_evidence") or [])
    engineering = deepcopy(
        (result.get("engineering_signals") or {}).get("signals") or
        synthesis.get("engineering_evidence") or []
    )
    historical = deepcopy(memory.get("incidents") or [])
    fleet_metrics = deepcopy(fleet.get("metrics") or {})
    fleet_limitations = list(fleet.get("limitations") or [])
    if FLEET_LIMITATION not in fleet_limitations:
        fleet_limitations.append(FLEET_LIMITATION)

    diagnosis = ml.get("diagnosis")
    assessment = []
    if state is not None:
        assessment.append({
            "kind": "reliability_state",
            "statement": f"Genesis reliability state is {state}.",
            "source": "reliability_state",
        })
    for statement in summary.get("what_is_unusual") or []:
        assessment.append({
            "kind": "existing_evidence_summary",
            "statement": statement,
            "source": "EvidenceSynthesis",
        })
    if diagnosis:
        assessment.append({
            "kind": "diagnosis_inference",
            "label": "Genesis diagnosis / inference",
            "diagnosis": deepcopy(diagnosis),
            "source": "DiagnosisEngine",
            "statement": _diagnosis_statement(diagnosis),
        })
    for contradiction in synthesis.get("contradictions") or []:
        if contradiction.get("resolved") is False:
            assessment.append({
                "kind": "evidence_tension",
                "statement": "Genesis cannot resolve this evidence tension from the available data.",
                "evidence_statement": contradiction.get("statement"),
                "source": deepcopy(contradiction.get("sources") or []),
            })

    unknowns = []
    for value in (
        result.get("limitations") or []
    ) + (
        synthesis.get("missing_evidence") or []
    ) + (
        synthesis.get("limitations") or []
    ):
        if isinstance(value, str) and value and value not in unknowns:
            unknowns.append(value)
    missing_fields = (result.get("capability_discovery") or {}).get("missing_telemetry") or []
    if missing_fields:
        unknowns.append("Not observed: " + ", ".join(missing_fields))

    recommendation_items = []
    if recommendation.get("recommendation"):
        recommendation_items.append({
            "text": recommendation["recommendation"],
            "risk_level": recommendation.get("risk_level"),
            "priority": recommendation.get("priority"),
            "source": "RecommendationEngine",
        })

    lifecycle = {}
    for field in ("status", "start_time_step", "end_time_step", "incident_type"):
        if field in incident:
            lifecycle[field] = incident[field]

    sampling = deepcopy(result.get("sampling_analysis") or {})
    timeline = deepcopy(
        result.get("evidence_timeline") or result.get("timeline") or
        {"event_count": 0, "events": []}
    )

    report = {
        "report_version": "0.1",
        "robot": robot,
        "investigation": {
            "state": state,
            "incident_id": incident.get("incident_id"),
            "lifecycle": lifecycle,
        },
        "what_happened": what_happened,
        "observed_patterns": patterns,
        "engineering_signals": engineering,
        "ml_inference": ml,
        "historical_context": historical,
        "historical_comparison": historical_comparison,
        "fleet_context": {
            "status": fleet.get("status"),
            "peer_group": deepcopy(fleet.get("peer_group")),
            "comparable_robot_count": fleet.get("comparable_robot_count"),
            "metrics": fleet_metrics,
            "limitations": fleet_limitations,
        },
        "assessment": assessment,
        "recommendation": recommendation_items,
        "human_action": action,
        "outcome": outcome,
        "unknowns_and_limitations": unknowns,
        "evidence_tension": deepcopy(synthesis.get("contradictions") or []),
        "evidence_timeline": _timeline_report(timeline, sampling),
    }
    # Enforce the documented JSON-compatible report contract without mutating
    # the input result or silently accepting NaN/Infinity.
    try:
        return json.loads(json.dumps(report, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"investigation report is not JSON-compatible: {exc}") from exc


def render_investigation_report(report):
    """Render a deterministic plain-text report from a report dictionary."""
    if not isinstance(report, dict):
        raise ValueError("investigation report must be an object")
    robot = report.get("robot") or {}
    investigation = report.get("investigation") or {}
    identity = " | ".join(
        str(value) for value in (
            robot.get("robot_id"),
            " ".join(str(value) for value in (robot.get("manufacturer"), robot.get("robot_type")) if value),
        ) if value
    ) or "Unavailable"
    lines = [
        "==================================================",
        "GENESIS INVESTIGATION REPORT",
        "==================================================",
        "",
        "ROBOT",
        identity,
        "",
        "STATE",
        str(investigation.get("state") or "Unavailable"),
        "",
        _section("WHAT HAPPENED", _what_happened_lines(report.get("what_happened") or [])),
        _section("OBSERVED PATTERNS", _pattern_lines(report.get("observed_patterns") or [])),
        _section("ENGINEERING SIGNALS", _engineering_lines(report.get("engineering_signals") or [])),
        _section("ML INFERENCE", _ml_lines(report.get("ml_inference") or {})),
        _section("HISTORICAL CONTEXT", _history_lines(report.get("historical_context") or [])),
        _section("HISTORICAL COMPARISON", _historical_comparison_lines(
            report.get("historical_comparison") or {}
        )),
        _section("FLEET CONTEXT", _fleet_lines(report.get("fleet_context") or {})),
        _section("ASSESSMENT", _assessment_lines(report.get("assessment") or [])),
        _section("RECOMMENDATION", _recommendation_lines(report.get("recommendation") or [])),
        _section("UNKNOWN / LIMITATIONS", _bullet_lines(report.get("unknowns_and_limitations") or [])),
        _section("HUMAN ACTION", _action_lines(report.get("human_action") or {})),
        _section("OUTCOME", _outcome_lines(report.get("outcome") or {})),
        _section("EVIDENCE TENSION", _tension_lines(report.get("evidence_tension") or [])),
        _section("EVIDENCE TIMELINE", _timeline_lines(report.get("evidence_timeline") or {})),
        "==================================================",
    ]
    return "\n".join(lines)


def build_field_session_report(session):
    """Build a report from the latest existing Genesis result in a field session.

    Timeline events are concatenated from the already-recorded per-observation
    Genesis results; no events are synthesized.
    """
    if not isinstance(session, dict):
        raise ValueError("field session must be an object")
    results = session.get("genesis_results") or []
    if not results:
        raise ValueError("field session contains no Genesis investigation results")
    entries = [entry.get("result") for entry in results if isinstance(entry, dict)]
    entries = [entry for entry in entries if isinstance(entry, dict)]
    if not entries:
        raise ValueError("field session contains no valid Genesis investigation result")
    latest = deepcopy(entries[-1])
    events = []
    for entry in entries:
        events.extend((entry.get("evidence_timeline") or {}).get("events", []))
    events.sort(key=lambda event: (event.get("time_step", 0), event.get("event_type", "")))
    latest["evidence_timeline"] = {"event_count": len(events), "events": events}
    observed_telemetry = []
    for index, observation in enumerate(session.get("observations") or []):
        telemetry = observation.get("telemetry") or {}
        if telemetry.get("motor_temperature") is not None:
            observed_telemetry.append({
                "robot_id": ((session.get("session") or {}).get("robot") or {}).get("robot_id"),
                "time_step": telemetry.get("time_step"),
                "motor_temperature": telemetry["motor_temperature"],
            })
    if observed_telemetry:
        latest["processing"] = {
            "observation_count": len(session.get("observations") or []),
            "telemetry": observed_telemetry,
        }
    report = build_investigation_report(latest)
    # The configured context is session metadata and is preserved as report context.
    context = (session.get("session") or {}).get("sampling_context")
    report["field_session"] = {
        "session_id": (session.get("session") or {}).get("session_id"),
        "sampling_context": deepcopy(context),
    }
    return report


def _evidence_item(item):
    return {
        key: deepcopy(item[key])
        for key in ("evidence_id", "statement", "source", "supporting_data")
        if key in item
    }


def _motor_temperature_trajectory(processing):
    readings = [
        entry for entry in processing.get("telemetry", [])
        if entry.get("motor_temperature") is not None
    ]
    if not readings:
        return None
    values = [entry["motor_temperature"] for entry in readings]
    if len(readings) == 1:
        statement = f"Motor temperature was observed at {_format_value(values[0])}°C."
    else:
        sequence = " → ".join(f"{_format_value(value)}°C" for value in values)
        statement = f"Motor temperature observations: {sequence}."
    return {
        "evidence_id": "OBS-motor-temperature-trajectory",
        "statement": statement,
        "source": "Genesis processing telemetry",
        "supporting_data": deepcopy(readings),
    }


def _format_value(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:g}"
    return str(value)


def _diagnosis_statement(diagnosis):
    parts = []
    if diagnosis.get("failure_type"):
        parts.append(f"possible {diagnosis['failure_type']}")
    if diagnosis.get("probable_cause"):
        parts.append(str(diagnosis["probable_cause"]))
    detail = "; ".join(parts) or "existing diagnosis output"
    confidence = diagnosis.get("confidence")
    if confidence is not None:
        detail += f" (confidence {confidence})"
    return f"Genesis diagnosis / inference: {detail}."


def _timeline_report(timeline, sampling):
    count = sampling.get("source_timestamp_count")
    total = sampling.get("timestamp_count")
    if count is None or total is None:
        time_basis = "time_step; source timestamp provenance unavailable"
    elif count == 0:
        time_basis = "ingestion order; source timestamps unavailable"
    elif count < total:
        time_basis = "mixed; some source timestamps unavailable"
    else:
        time_basis = "source time_step"
    return {
        "time_basis": time_basis,
        "event_count": timeline.get("event_count", len(timeline.get("events") or [])),
        "events": deepcopy(timeline.get("events") or []),
    }


def _section(title, body):
    content = body or ["Unavailable — no existing evidence was provided."]
    return "\n".join(["--------------------------------------------------", title, "--------------------------------------------------", *content])


def _bullet_lines(values):
    return [f"- {value}" for value in values] or ["- None reported."]


def _what_happened_lines(items):
    return [f"- {item.get('statement')}" for item in items if item.get("statement")]


def _pattern_lines(patterns):
    if not patterns:
        return ["- No detectable telemetry patterns were recorded."]
    lines = []
    for item in patterns:
        supporting = item.get("supporting_data") or {}
        name = supporting.get("pattern", item.get("statement", "Observed pattern"))
        metric = supporting.get("affected_telemetry")
        window = supporting.get("window") or {}
        detail = f"{name}"
        if metric:
            detail += f" — {metric}"
        if window.get("start_time_step") is not None and window.get("end_time_step") is not None:
            detail += f" (time_step {window['start_time_step']}–{window['end_time_step']})"
        lines.append(f"- {detail}")
        if item.get("statement"):
            lines.append(f"  {item['statement']}")
        metrics = supporting.get("metrics") or {}
        concise_metrics = {
            key: value for key, value in metrics.items()
            if key not in {"changes", "coobserved_indices", "spike_time_steps"}
        }
        if concise_metrics:
            lines.append("  Metrics: " + _compact_mapping(concise_metrics))
    return lines


def _engineering_lines(signals):
    if not signals:
        return ["- No engineering signals were recorded."]
    return [
        f"- {item.get('signal', 'Engineering signal')}: {item.get('message') or ''}".rstrip()
        + (f" (value: {_format_value(item['value'])})" if item.get("value") is not None else "")
        for item in signals
    ]


def _ml_lines(ml):
    if not ml.get("prediction_available"):
        unavailable = next((item for item in ml.get("evidence", [])
                            if item.get("evidence_id") == "ML-risk-unavailable"), None)
        reason = "; ".join((unavailable or {}).get("limitations") or [])
        return ["- Unavailable" + (f" — {reason}" if reason else ".")]
    probability = ml.get("probability")
    lines = [f"- Failure probability: {_format_value(probability)}" if probability is not None
             else "- Model inference available; probability not provided."]
    if ml.get("model_prediction") is not None:
        lines.append(f"- Model prediction: {ml['model_prediction']}")
    if ml.get("diagnosis"):
        lines.append("- " + _diagnosis_statement(ml["diagnosis"]))
    return lines


def _history_lines(incidents):
    if not incidents:
        return ["- No matching historical incidents were found."]
    lines = [f"- {len(incidents)} similar incident(s) found."]
    for item in incidents:
        lines.append(f"- {item.get('incident_id', 'Incident')}: "
                     f"match reasons: {', '.join(item.get('similarity_reasons') or []) or 'not provided'}")
        diagnosis = item.get("diagnosis") or {}
        recommendation = item.get("recommendation") or {}
        action = item.get("human_action") or {}
        outcome = item.get("outcome") or {}
        signals = item.get("engineering_signals") or []
        if signals:
            lines.append("  Previous signals: " + ", ".join(str(value) for value in signals))
        if diagnosis.get("possible_failure_type") or diagnosis.get("probable_cause"):
            lines.append("  Previous diagnosis/inference: " + "; ".join(
                str(value) for value in (diagnosis.get("possible_failure_type"), diagnosis.get("probable_cause")) if value
            ))
        if recommendation.get("text"):
            lines.append(f"  Previous recommendation: {recommendation['text']}")
        for value in action.get("items") or []:
            lines.append(f"  Previous human action: {value}")
        if outcome.get("details"):
            lines.append("  Previous outcome: " + _compact_mapping(outcome["details"]))
    return lines


def _historical_comparison_lines(comparison):
    lines = [f"- Comparison status: {comparison.get('status', 'UNAVAILABLE')}."]
    baseline = comparison.get("baseline_visibility") or comparison.get("baseline") or {}
    if baseline:
        lines.append(f"- Baseline status: {baseline.get('status', 'UNAVAILABLE')}.")
        if baseline.get("reason"):
            lines.append(f"- Baseline reason: {baseline['reason']}")
        lines.append(
            "- Eligible baseline records: "
            f"{baseline.get('eligible_records', 0)} / {baseline.get('required_records', 'unknown')} required."
        )
    elif comparison.get("message"):
        lines.append(f"- {comparison['message']}")
    metrics = comparison.get("comparison_metrics") or {}
    if metrics:
        lines.append("- Comparison metrics: " + _compact_mapping(metrics))
    return lines


def _fleet_lines(fleet):
    lines = []
    if fleet.get("comparable_robot_count") is not None:
        lines.append(f"- Comparable peers: {fleet['comparable_robot_count']}")
    if fleet.get("peer_group"):
        lines.append(f"- Peer group: {_compact_mapping(fleet['peer_group'])}")
    for metric, values in (fleet.get("metrics") or {}).items():
        parts = []
        for key in ("peer_mean", "peer_minimum", "peer_maximum", "robot_value", "current_value", "status"):
            if values.get(key) is not None:
                label = {"peer_minimum": "peer_min", "peer_maximum": "peer_max",
                         "robot_value": "current_robot", "current_value": "current"}.get(key, key)
                parts.append(f"{label}={values[key]}")
        if parts:
            lines.append(f"- {metric}: " + ", ".join(parts))
    lines.extend(f"- Limitation: {value}" for value in fleet.get("limitations") or [])
    return lines


def _assessment_lines(items):
    lines = []
    for item in items:
        if item.get("kind") == "evidence_tension":
            lines.append(f"- {item.get('statement')} {item.get('evidence_statement') or ''}".rstrip())
        else:
            lines.append(f"- {item.get('statement')}")
    return lines


def _recommendation_lines(items):
    return [f"- {item.get('text')}" for item in items if item.get("text")]


def _action_lines(action):
    items = action.get("items") or []
    status = action.get("status", "PENDING").capitalize()
    return [f"- {status}: {item}" for item in items] or [f"- {status}"]


def _outcome_lines(outcome):
    details = outcome.get("details")
    if details:
        return [f"- {outcome.get('status', 'Recorded')}: {_compact_mapping(details)}"]
    return [f"- {outcome.get('status', 'OUTCOME_PENDING').replace('_', ' ').capitalize()}"]


def _tension_lines(tensions):
    if not tensions:
        return ["- No unresolved evidence tensions were recorded."]
    lines = []
    for item in tensions:
        lines.append(f"- {item.get('statement', 'Evidence tension recorded.')}")
        if item.get("resolved") is False:
            lines.append("  Genesis cannot resolve this evidence tension from the available data.")
    return lines


def _timeline_lines(timeline):
    events = timeline.get("events") or []
    if not events:
        return ["- No existing timeline events are available."]
    basis = timeline.get("time_basis", "time_step; source timestamp provenance unavailable")
    lines = [f"- Time basis: {basis}"]
    for event in events:
        step = event.get("time_step")
        if timeline.get("time_basis", "").startswith("ingestion order"):
            label = f"Observation {step} (ingestion order)"
        else:
            label = f"time_step {step}" if step is not None else "Time unavailable"
        lines.append(f"- {label} — {event.get('description', event.get('event_type', 'event'))}")
    return lines


def _compact_mapping(value):
    if isinstance(value, dict):
        return ", ".join(f"{key}={value[key]}" for key in sorted(value))
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Render a Genesis investigation or field session report.")
    parser.add_argument("--input", required=True, help="Genesis result JSON or Field Agent field-session JSON")
    parser.add_argument("--output", help="Optional UTF-8 text report path")
    args = parser.parse_args(argv)
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = build_field_session_report(data) if "genesis_results" in data else build_investigation_report(data)
    rendered = render_investigation_report(report)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        print(f"Saved Genesis investigation report: {args.output}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
