"""Structured incident report assembled from EvidenceSynthesis outputs."""

from evidence_synthesis import (
    ENGINEERING_SIGNAL,
    FLEET_COMPARISON,
    HISTORICAL_COMPARISON,
    ML_INFERENCE,
    OBSERVATION,
    EvidenceSynthesis,
)


def _incident_data(incident, result):
    if hasattr(incident, "summary"):
        return incident.summary()
    return incident or result.get("incident") or {}


class IncidentExplanation:
    """Presentation model; its evidence fields come from EvidenceSynthesis."""

    @classmethod
    def build(
        cls,
        result,
        feature_record,
        incident=None,
        historical_memory=None,
        fleet_context=None,
        evidence_synthesis=None,
        synthesis_engine=None,
    ):
        incident_data = _incident_data(incident, result)
        risk = result.get("risk") or {}
        quality = result.get("observation_quality") or risk.get("observation_quality") or {}
        fleet_context = fleet_context or result.get("fleet_context")
        memory = historical_memory or {
            "status": "UNAVAILABLE", "match_count": 0, "incidents": [],
            "message": "historical memory unavailable",
        }
        if evidence_synthesis is None:
            evidence_synthesis = (synthesis_engine or EvidenceSynthesis()).synthesize(
                feature_record=feature_record,
                observation_quality=quality,
                risk_result=risk,
                diagnosis=result.get("diagnosis"),
                recommendation=result.get("recommendation"),
                incident=incident_data,
                comparison=result.get("comparison"),
                baseline=result.get("baseline"),
                fleet_context=fleet_context,
                historical_memory=memory,
                timeline=result.get("timeline"),
                telemetry_patterns=result.get("telemetry_patterns"),
            )

        engineering = risk.get("engineering") or (risk.get("fusion") or {}).get("engineering") or {}
        diagnosis = result.get("diagnosis")
        historical_comparison = {
            "status": "AVAILABLE" if (
                (result.get("comparison") or {}).get("metrics")
                or (result.get("baseline") or {}).get("metrics")
            ) else "UNAVAILABLE",
            "comparison": result.get("comparison"),
            "baseline": result.get("baseline"),
            "message": None if (
                (result.get("comparison") or {}).get("metrics")
                or (result.get("baseline") or {}).get("metrics")
            ) else "historical comparison unavailable",
        }
        observations = evidence_synthesis["observations"]
        temporal = evidence_synthesis["temporal_evidence"]
        engineering_items = evidence_synthesis["engineering_evidence"]
        ml_items = evidence_synthesis["ml_evidence"]
        fleet_items = evidence_synthesis["fleet_evidence"]
        historical_items = evidence_synthesis["historical_evidence"]
        pattern_items = evidence_synthesis.get("pattern_evidence", [])
        sampling_items = evidence_synthesis.get("sampling_evidence", [])
        evidence_summary = {
            "temporal": temporal,
            "patterns": pattern_items,
            "sampling_context": sampling_items,
            "thermal": [item for item in observations if item["category"] == "thermal"],
            "battery": [item for item in observations if item["category"] == "battery"],
            "workload": [item for item in observations if item["category"] == "workload"],
            "fleet_history": historical_items,
            "fleet_comparison": fleet_items,
            "engineering_signals": engineering_items,
            "ml_inference": ml_items,
            "observation_quality": evidence_synthesis["quality_evidence"],
        }
        status = incident_data.get("status", "NO_INCIDENT")
        quality_summary = evidence_synthesis["observation_quality"]
        fusion_final = (risk.get("fusion") or {}).get("final", {})
        return {
            "identity": {
                "incident_id": incident_data.get("incident_id"),
                "robot_id": result.get("robot_id", feature_record.get("robot_id")),
                "site_id": incident_data.get("site_id", feature_record.get("site_id")),
                "manufacturer": feature_record.get("manufacturer", incident_data.get("manufacturer")),
                "robot_type": feature_record.get("robot_type", incident_data.get("robot_type")),
                "start_time_step": incident_data.get("start_time_step"),
                "end_time_step": incident_data.get("end_time_step"),
                "status": status,
                "incident_type": incident_data.get("incident_type"),
            },
            "lifecycle": {
                "status": status,
                "start_time_step": incident_data.get("start_time_step"),
                "end_time_step": incident_data.get("end_time_step"),
            },
            "reliability_state": {
                "current": result.get("state"),
                "previous": result.get("previous_state"),
                "transition": result.get("state_transition"),
            },
            "observation_quality": quality_summary,
            "observations": observations,
            "temporal_evidence": temporal,
            "pattern_evidence": pattern_items,
            "sampling_evidence": sampling_items,
            "sampling_analysis": evidence_synthesis.get("sampling_analysis", {}),
            "pattern_analysis": evidence_synthesis.get("pattern_analysis", {}),
            "historical_evidence": historical_comparison,
            "historical_memory": memory,
            "engineering_signals": {
                "severity": engineering.get("severity"),
                "status": engineering.get("status"),
                "items": engineering_items,
            },
            "ml_inference": {
                "prediction_available": bool(risk.get("prediction_available", risk.get("probability") is not None)),
                "predicted_risk": risk.get("fused_risk", fusion_final.get("risk")),
                "probability": risk.get("probability"),
                "model_prediction": risk.get("model_prediction"),
                "operational_prediction": risk.get("prediction"),
                "diagnosis": ({
                    "possible_failure_type": diagnosis.get("failure_type"),
                    "probable_cause": diagnosis.get("probable_cause"),
                    "confidence": diagnosis.get("confidence"),
                    "confirmed": False,
                } if diagnosis is not None else None),
                "evidence": ml_items,
            },
            "fleet_peer_context": fleet_context or {
                "status": "INSUFFICIENT_DATA", "type": FLEET_COMPARISON,
                "peer_group": None, "comparable_robot_count": 0, "metrics": {},
                "limitations": ["fleet comparison unavailable: no peer observations"],
                "message": "Fleet comparison unavailable: insufficient comparable robots.",
            },
            "evidence_summary": evidence_summary,
            "evidence_synthesis": evidence_synthesis,
            "contradictions": evidence_synthesis["contradictions"],
            "missing_evidence": evidence_synthesis["missing_evidence"],
            "recommendation": evidence_synthesis["recommendation"],
            "human_action": evidence_synthesis["human_action"],
            "outcome": evidence_synthesis["outcome"],
            "limitations": evidence_synthesis["limitations"],
        }
