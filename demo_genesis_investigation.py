"""Deterministic, controlled end-to-end Genesis investigation demonstration."""

from baseline_engine import BaselineEngine
from comparison_engine import ComparisonEngine
from decision_pipeline import DecisionPipeline
from evidence_engine import EvidenceEngine
from evidence_synthesis import EvidenceSynthesis
from fleet_baseline import FleetBaseline
from history import History
from incident_explanation import IncidentExplanation
from incident_manager import IncidentManager
from recommendation_engine import RecommendationEngine
from reliability_memory import ReliabilityMemory
from reliability_state import ReliabilityState
from telemetry_features import TelemetryFeatureBuilder


ROBOT = {"robot_id": "R004", "manufacturer": "ABB", "robot_type": "AMR"}
TEMPERATURES = (42, 44, 47, 52, 58, 61, 49, 44)
WORKLOADS = (35, 36, 38, 42, 48, 52, 40, 35)
ENGINEERING_SIGNAL = "critical_motor_temperature"
MODEL_UNAVAILABLE_REASON = "No fitted model artifact available for this demonstration."


def demo_telemetry_records(count=8):
    """Return the R004 demo's normalized source telemetry, before feature building."""
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= len(TEMPERATURES):
        raise ValueError(f"count must be an integer from 1 to {len(TEMPERATURES)}")
    records = []
    for step in range(1, count + 1):
        records.append({
            **ROBOT,
            "time_step": step,
            "motor_temperature": float(TEMPERATURES[step - 1]),
            "ambient_temperature": 22.0,
            "battery_level": 80.0,
            "battery_voltage": 48.0,
            "battery_current": 12.0,
            "battery_temperature": 30.0,
            "power_consumption": 800.0,
            "voltage_drop": 0.5,
            "workload": float(WORKLOADS[step - 1]),
            "robot_state": "working",
        })
    return records


def demo_peer_records():
    """Expose the same fixed peer observations used by the investigation demo."""
    return _peer_records()


def demo_historical_incidents():
    """Expose the same sample history used by the investigation demo."""
    return [
        _historical_incident(
            "HIST-INC-001", "R004", "ABB", "AMR", "Motor bearing replaced.",
        ),
        _historical_incident(
            "HIST-INC-002", "R002", "ABB", "AMR", "Inspection completed.",
        ),
    ]


def _historical_incident(incident_id, robot_id, manufacturer, robot_type, outcome):
    """Seed the existing ReliabilityMemory schema with labeled sample history."""
    report = {
        "identity": {
            "incident_id": incident_id,
            "robot_id": robot_id,
            "manufacturer": manufacturer,
            "robot_type": robot_type,
            "incident_type": "thermal_observation",
            "status": "CLOSED",
            "start_time_step": 1,
            "end_time_step": 2,
        },
        "reliability_state": {"current": "HEALTHY", "previous": "RECOVERING"},
        "engineering_signals": {"items": [{"signal": ENGINEERING_SIGNAL}]},
        "recommendation": {
            "status": "AVAILABLE",
            "text": "Inspect motor assembly.",
        },
        "human_action": {
            "status": "RECORDED",
            "items": ["Technician inspected motor assembly."],
        },
        "outcome": {
            "status": "RESOLVED",
            "resolved": True,
            "details": {"description": outcome, "dataset": "CONTROLLED SIMULATION"},
        },
        "observations": [],
        "temporal_evidence": [],
        "observation_quality": {"overall": "AVAILABLE"},
        "limitations": ["Seeded historical sample for the controlled demo."],
    }
    return report


def _seed_memory():
    memory = ReliabilityMemory()
    for report in demo_historical_incidents():
        memory.store_incident(report)
    return memory


def _peer_records():
    peers = []
    peer_data = (
        ("R001", "ABB", "AMR", 42.0),
        ("R002", "ABB", "AMR", 43.0),
        ("R003", "ABB", "AMR", 44.0),
        ("R005", "KUKA", "robotic_arm", 70.0),
    )
    for robot_id, manufacturer, robot_type, temperature in peer_data:
        peers.append({
            "robot_id": robot_id,
            "manufacturer": manufacturer,
            "robot_type": robot_type,
            "time_step": 6,
            "motor_temperature": temperature,
            "ambient_temperature": 22.0,
            "thermal_rise": round(temperature - 22.0, 2),
            "battery_level": 80.0,
            "battery_voltage": 48.0,
            "battery_current": 12.0,
            "battery_temperature": 30.0,
            "power_consumption": 800.0,
            "voltage_drop": 0.5,
            "workload": 45.0,
        })
    return peers


def _telemetry(builder, step):
    return builder.build({
        "identity": ROBOT,
        "telemetry": {
            "time_step": step,
            "motor_temperature": float(TEMPERATURES[step - 1]),
            "ambient_temperature": 22.0,
            "battery_level": 80.0,
            "battery_voltage": 48.0,
            "battery_current": 12.0,
            "battery_temperature": 30.0,
            "power_consumption": 800.0,
            "voltage_drop": 0.5,
            "workload": float(WORKLOADS[step - 1]),
            "robot_state": "working",
        },
    })


def _memory_query(robot_id="R004"):
    return {
        "identity": {
            "robot_id": robot_id,
            "manufacturer": "ABB",
            "robot_type": "AMR",
        },
        "engineering_signals": {"items": [{"signal": ENGINEERING_SIGNAL}]},
    }


def _merge_timelines(results):
    events = []
    for result in results:
        events.extend(result.get("timeline", {}).get("events", []))
    events.sort(key=lambda event: (event.get("time_step", 0), event.get("event_type", "")))
    return {"event_count": len(events), "events": events}


def run_demo():
    """Run the fixed scenario and return the source component results."""
    history = History()
    incident_manager = IncidentManager(history)
    memory = _seed_memory()
    fleet_baseline = FleetBaseline()
    builder = TelemetryFeatureBuilder()
    pipeline = DecisionPipeline(
        prediction_engine=None,
        diagnosis_engine=None,
        recommendation_engine=RecommendationEngine(),
        reliability_state=ReliabilityState(),
        incident_manager=incident_manager,
        evidence_engine=EvidenceEngine(),
        comparison_engine=ComparisonEngine(history_window=10),
        baseline_engine=BaselineEngine(minimum_records=10),
        reliability_memory=memory,
        fleet_baseline=fleet_baseline,
    )

    records = []
    results = []
    lifecycle = []
    previous_state = None
    peers = _peer_records()
    for step in range(1, 9):
        record = _telemetry(builder, step)
        records.append(record)
        result = pipeline.evaluate(
            record,
            previous_state=previous_state,
            historical_records=records[:-1],
            fleet_records=peers if step == 6 else [],
        )
        results.append(result)
        previous_state = result["state"]
        current_incident = incident_manager.get_active_incident(ROBOT["robot_id"])
        lifecycle.append({
            "time_step": step,
            "reliability_state": result["state"],
            "incident_status": current_incident.status if current_incident else "NO_INCIDENT",
        })

        if step == 6:
            incident = current_incident
            incident.add_action("Technician inspected motor assembly.")
        elif step == 7:
            incident = incident_manager.mark_recovering(ROBOT["robot_id"], step)
            lifecycle[-1]["incident_status"] = incident.status
            incident.set_outcome({
                "demo_label": "SIMULATED DEMO OUTCOME",
                "description": "Motor bearing wear found and bearing replaced.",
            })

    incident = incident_manager.get_active_incident(ROBOT["robot_id"])
    if incident is None:
        raise RuntimeError("The existing pipeline did not create the expected incident.")
    incident = incident_manager.close_incident(
        ROBOT["robot_id"],
        end_time_step=8,
        outcome={
            "resolved": True,
            "final_state": "CLOSED",
            "resolution_time_step": 8,
            "demo_label": "SIMULATED DEMO OUTCOME",
        },
    )
    lifecycle[-1]["incident_status"] = incident.status

    critical_result = results[5]
    final_timeline = _merge_timelines(results[5:])
    historical_memory = memory.historical_context(
        _memory_query(), exclude_incident_id=incident.incident_id,
    )
    final_synthesis = EvidenceSynthesis().synthesize(
        feature_record=records[5],
        observation_quality=critical_result["observation_quality"],
        risk_result=critical_result["risk"],
        diagnosis=critical_result["diagnosis"],
        recommendation=critical_result["recommendation"],
        incident=incident,
        comparison=critical_result["comparison"],
        baseline=critical_result["baseline"],
        fleet_context=critical_result["fleet_context"],
        historical_memory=historical_memory,
        timeline=final_timeline,
    )
    final_result = dict(critical_result)
    final_result.update({"incident": incident.summary(), "timeline": final_timeline})
    explanation = IncidentExplanation.build(
        final_result,
        records[5],
        incident=incident,
        historical_memory=historical_memory,
        fleet_context=critical_result["fleet_context"],
        evidence_synthesis=final_synthesis,
    )
    memory.update_incident(incident, explanation)
    future_memory = memory.historical_context(_memory_query())

    return {
        "dataset": "CONTROLLED SIMULATION",
        "identity": dict(ROBOT),
        "records": records,
        "critical_result": critical_result,
        "lifecycle": lifecycle,
        "incident": incident.summary(),
        "explanation": explanation,
        "future_memory_context": future_memory,
        "peer_input": peers,
        "memory_entries": memory.entries,
    }


def _format_report(report):
    explanation = report["explanation"]
    identity = explanation["identity"]
    quality = explanation["observation_quality"]
    fleet = explanation["fleet_peer_context"]
    motor = fleet.get("metrics", {}).get("motor_temperature", {})
    historical = explanation["historical_memory"]
    engineering = explanation["engineering_signals"].get("items", [])
    ml = explanation["ml_inference"]
    synthesis = explanation["evidence_synthesis"]
    recommendation = explanation["recommendation"]
    action = explanation["human_action"]
    outcome = explanation["outcome"]
    lines = [
        "========================================",
        "GENESIS RELIABILITY INVESTIGATION",
        "========================================",
        f"DATASET: {report['dataset']}",
        "",
        "ROBOT",
        f"{identity['robot_id']} | {identity['manufacturer']} / {identity['robot_type']}",
        "Initial observation: 42°C at t=1 (normal telemetry baseline; model state remains WATCH while evidence warms up).",
        "",
        "INCIDENT",
        f"{identity['incident_id']} | lifecycle: {identity['status']} | reliability state at signal: {report['critical_result']['state']}",
        "",
        "WHAT CHANGED",
        "Motor temperature: " + " → ".join(f"{value}°C" for value in TEMPERATURES[:6]),
        "",
        "ENGINEERING SIGNALS",
    ]
    lines.extend(
        f"{item.get('signal')}: {item.get('message')} (value={item.get('value')})"
        for item in engineering
    )
    lines.extend([
        "",
        "FLEET CONTEXT",
        f"Peer group: ABB / AMR | comparable peers: {fleet.get('comparable_robot_count')}",
        f"Motor temperature: R004={motor.get('robot_value')}°C; peer mean={motor.get('peer_mean')}°C; range={motor.get('peer_minimum')}–{motor.get('peer_maximum')}°C; {motor.get('status')} (context, not proof of failure).",
        "KUKA / robotic_arm R005 excluded by the existing peer grouping.",
        "",
        "HISTORICAL MEMORY",
        f"{historical.get('match_count', 0)} previous incidents matched: " + ", ".join(
            item["incident_id"] for item in historical.get("incidents", [])
        ),
        "",
        "ML INFERENCE",
        "UNAVAILABLE",
        f"Reason: {ml.get('evidence', [{}])[0].get('limitations', [MODEL_UNAVAILABLE_REASON])[0] if ml.get('evidence') else MODEL_UNAVAILABLE_REASON}",
        "No risk probability was generated.",
        "",
        "OBSERVATION QUALITY",
        f"Overall: {quality.get('overall')} | thermal: {quality.get('thermal')} | battery: {quality.get('battery')} | workload: {quality.get('workload')}",
        "",
        "EVIDENCE SYNTHESIS",
        f"Status: {synthesis.get('summary', {}).get('status')}",
        "Evidence remains separated by source: telemetry, fleet comparison, engineering signal, ML inference, and historical comparison.",
        "",
        "RECOMMENDATION",
        recommendation.get("text") or "UNAVAILABLE",
        "",
        "HUMAN ACTION",
        "; ".join(action.get("items", [])) or "PENDING",
        "",
        "OUTCOME",
        "SIMULATED DEMO OUTCOME: " + str((outcome.get("details") or {}).get("description", "")),
        "",
        "LIMITATIONS",
    ])
    lines.extend(f"- {item}" for item in explanation.get("limitations", []))
    lines.extend([
        "",
        "========================================",
        "INCIDENT CLOSED",
        "========================================",
        "",
        "========================================",
        "MEMORY FEEDBACK",
        "========================================",
        "Future ABB / AMR query for critical_motor_temperature retrieved: "
        + ", ".join(item["incident_id"] for item in report["future_memory_context"].get("incidents", [])),
    ])
    return "\n".join(lines)


def main():
    report = run_demo()
    print(_format_report(report))


if __name__ == "__main__":
    main()
