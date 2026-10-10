"""Minimal operator CLI for the public Genesis investigation facade."""

import argparse
import json
import sys

from demo_genesis_investigation import (
    demo_historical_incidents,
    demo_peer_records,
    demo_telemetry_records,
)
from genesis import Genesis
from investigation_report import render_investigation_report, build_investigation_report


def run_controlled_investigation():
    """Run the existing R004 telemetry scenario through the public facade."""
    genesis = Genesis(
        peer_records=demo_peer_records(),
        historical_incidents=demo_historical_incidents(),
    )
    return genesis.investigate(demo_telemetry_records(count=6))


def _operator_report(result):
    robot = result["robot"]
    fleet = result.get("fleet_context", {})
    motor = fleet.get("metrics", {}).get("motor_temperature", {})
    historical = result.get("historical_memory", {})
    ml = result.get("ml_inference", {})
    recommendation = result.get("recommendation") or {}
    synthesis = result.get("evidence_synthesis", {}).get("summary", {})
    temperatures = [
        item.get("motor_temperature")
        for item in result.get("processing", {}).get("telemetry", [])
        if item.get("motor_temperature") is not None
    ]
    signal_names = [
        signal.get("signal")
        for signal in result.get("engineering_signals", {}).get("signals", [])
        if signal.get("signal")
    ]
    risk_evidence = next(
        (item for item in ml.get("evidence", []) if item.get("evidence_id") == "ML-risk-unavailable"),
        None,
    )
    ml_status = (
        "Unavailable — " + "; ".join(risk_evidence.get("limitations", []))
        if risk_evidence else f"Available — probability {ml.get('probability')}"
    )
    action_items = result.get("human_action", {}).get("items", [])
    outcome = result.get("outcome", {})
    outcome_details = outcome.get("details")
    outcome_text = str(outcome_details) if outcome_details else "Pending"
    quality = result.get("observation_quality", {}).get("groups", {})
    quality_status = {
        group: values.get("status", "UNAVAILABLE")
        for group, values in quality.items()
    }
    if temperatures:
        temperature_line = "Motor temperature:\n" + " → ".join(
            f"{value:g}°C" for value in temperatures
        )
    else:
        temperature_line = "Motor temperature history unavailable"
    if motor.get("status") == "OUTLIER":
        fleet_context = "R004 is an outlier"
    elif motor.get("status") in ("ELEVATED", "NORMAL"):
        fleet_context = motor.get("interpretation", motor["status"])
    else:
        fleet_context = "Peer comparison unavailable"
    known = []
    if temperatures:
        known.append(f"Motor temperature reached {temperatures[-1]:g}°C.")
    if motor.get("status") == "OUTLIER":
        known.append("R004 is significantly above comparable ABB/AMR peers.")
    if signal_names:
        known.append("Critical thermal engineering signals are present.")
    if historical.get("match_count", 0):
        known.append("Previous similar incidents exist.")
    unknown = synthesis.get("what_we_do_not_know") or result.get("limitations", [])
    recommendation_text = recommendation.get("recommendation") or "Unavailable"
    limitations = result.get("limitations", [])
    lines = [
        "========================================",
        "GENESIS INVESTIGATION",
        "========================================",
        "",
        "ROBOT",
        f"{robot.get('robot_id')} | {robot.get('manufacturer')} {robot.get('robot_type')}",
        "",
        "RELIABILITY STATE",
        str(result.get("reliability_state", {}).get("current", "UNAVAILABLE")),
        "",
        "WHAT CHANGED",
        temperature_line,
        "",
        "EVIDENCE",
        "Engineering:",
        *([
            f"• {name.replace('_', ' ').capitalize()}"
            for name in signal_names
        ] if signal_names else ["• No engineering signal detected"]),
        "",
        "Fleet:",
        f"• Peer mean: {motor.get('peer_mean'):g}°C" if isinstance(motor.get("peer_mean"), (int, float)) else "• Peer mean: Unavailable",
        (
            f"• Peer range: {motor['peer_minimum']:g}–{motor['peer_maximum']:g}°C"
            if isinstance(motor.get("peer_minimum"), (int, float)) and isinstance(motor.get("peer_maximum"), (int, float))
            else "• Peer range: Unavailable"
        ),
        f"• {fleet_context}",
        "• Context only — not proof of failure",
        "",
        "History:",
        f"• {historical.get('match_count', 0)} similar incidents found",
        "",
        "ML:",
        f"• {ml_status}",
        "",
        "OBSERVATION QUALITY",
        f"• Thermal: {quality_status.get('thermal', 'UNAVAILABLE')}",
        f"• Battery: {quality_status.get('battery', 'UNAVAILABLE')}",
        f"• Workload: {quality_status.get('workload', 'UNAVAILABLE')}",
        "",
        "WHAT GENESIS KNOWS",
        *([f"• {item}" for item in known] if known else ["• No synthesized evidence available"]),
        "",
        "WHAT GENESIS DOES NOT KNOW",
        *([f"• {item}" for item in unknown] if unknown else ["• No current unknowns were reported"]),
        "",
        "RECOMMENDATION",
        recommendation_text,
        "",
        "HUMAN ACTION",
        "; ".join(str(item) for item in action_items) if action_items else "Pending",
        "",
        "OUTCOME",
        outcome_text if outcome.get("status") != "OUTCOME_PENDING" else "Pending",
        "",
        "LIMITATIONS",
    ]
    lines.extend(f"• {item}" for item in limitations)
    if not limitations:
        lines.append("• None reported")
    lines.append("========================================")
    return "\n".join(lines)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run the controlled Genesis R004 investigation.")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="print the complete structured Genesis result as JSON")
    output.add_argument("--report", action="store_true", help="print a deterministic engineer-readable investigation report")
    args = parser.parse_args(argv)
    result = run_controlled_investigation()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    elif args.report:
        print(render_investigation_report(build_investigation_report(result)))
    else:
        print(_operator_report(result))


if __name__ == "__main__":
    main()
