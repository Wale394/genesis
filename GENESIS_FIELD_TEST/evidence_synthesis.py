"""Deterministic organization of existing Genesis evidence and decisions."""

from copy import deepcopy
import math
from numbers import Real

from feature_contract import DEPLOYABLE_FEATURES, RAW_FEATURES


OBSERVATION = "OBSERVATION"
HISTORICAL_COMPARISON = "HISTORICAL_COMPARISON"
ENGINEERING_SIGNAL = "ENGINEERING_SIGNAL"
ML_INFERENCE = "ML_INFERENCE"
FLEET_COMPARISON = "FLEET_COMPARISON"
PATTERN = "PATTERN"

OBSERVATION_FIELDS = (
    "motor_temperature", "ambient_temperature", "thermal_rise",
    "battery_level", "battery_voltage", "battery_current",
    "battery_temperature", "voltage_drop", "workload",
    "power_consumption", "robot_state",
)
TEMPORAL_FIELDS = tuple(
    field for field in DEPLOYABLE_FEATURES
    if field not in RAW_FEATURES and field != "thermal_rise"
)
THERMAL_FIELDS = frozenset({
    "motor_temperature", "ambient_temperature", "thermal_rise",
    "temperature_change", "temperature_rate_3", "temperature_rate_5",
    "temperature_avg_3", "temperature_avg_5", "thermal_rise_rate_3",
    "thermal_rise_max_3", "thermal_rise_max_5", "thermal_rise_avg_3",
    "thermal_rise_avg_5", "thermal_elevated_persistence", "temperature_acceleration",
})
BATTERY_FIELDS = frozenset({
    "battery_level", "battery_voltage", "battery_current", "battery_temperature",
    "voltage_drop", "battery_change", "battery_drop_rate_3", "battery_voltage_change",
    "battery_voltage_drop_rate_3", "battery_current_change", "battery_temperature_change",
    "battery_temperature_rate_3", "battery_decline_3", "battery_decline_5",
    "low_battery_persistence", "battery_voltage_decline_3", "battery_current_change_3",
})
WORKLOAD_FIELDS = frozenset({"workload", "power_consumption", "power_change", "power_rate_3"})


def _category(field):
    if field in THERMAL_FIELDS:
        return "thermal"
    if field in BATTERY_FIELDS:
        return "battery"
    if field in WORKLOAD_FIELDS:
        return "workload"
    return "temporal"


def _readable(field):
    return field.replace("_", " ")


def _item(evidence_id, category, evidence_type, statement, source, supporting_data=None,
          availability="AVAILABLE", confidence=None, limitations=None):
    return {
        "evidence_id": evidence_id,
        "category": category,
        "evidence_type": evidence_type,
        "type": evidence_type,
        "statement": statement,
        "source": source,
        "confidence": confidence,
        "availability": availability,
        "supporting_data": deepcopy(supporting_data or {}),
        "limitations": list(limitations or []),
    }


def _quality_status(value):
    if value in ("AVAILABLE", "DEGRADED", "INSUFFICIENT"):
        return value
    return "UNAVAILABLE"


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Real) and not isinstance(value, bool):
        number = float(value)
        if not math.isfinite(number):
            return None
        return value.item() if hasattr(value, "item") else value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class EvidenceSynthesis:
    """Read and organize source results without changing inference or decisions."""

    def synthesize(
        self,
        feature_record,
        observation_quality=None,
        risk_result=None,
        diagnosis=None,
        recommendation=None,
        incident=None,
        comparison=None,
        baseline=None,
        fleet_context=None,
        historical_memory=None,
        timeline=None,
        telemetry_patterns=None,
        sampling_analysis=None,
    ):
        observation_quality = deepcopy(observation_quality or {})
        risk_result = risk_result or {}
        diagnosis = diagnosis or None
        recommendation = recommendation or {}
        incident = incident.summary() if hasattr(incident, "summary") else (incident or {})
        comparison = comparison or {}
        baseline = baseline or {}
        fleet_context = fleet_context or {}
        historical_memory = historical_memory or {
            "status": "UNAVAILABLE", "match_count": 0, "incidents": [],
            "message": "historical memory unavailable",
        }
        timeline = timeline or {}
        telemetry_patterns = telemetry_patterns or {}
        sampling_analysis = sampling_analysis or {}

        observations = []
        temporal = []
        for field in OBSERVATION_FIELDS:
            value = feature_record.get(field)
            if value is None or value == "":
                continue
            category = _category(field)
            item = _item(
                f"OBS-{field}", category, OBSERVATION,
                f"Observed {_readable(field)}: {value}.", "telemetry",
                {"field": field, "value": value},
            )
            item.update({"field": field, "value": value})
            observations.append(item)
        for field in TEMPORAL_FIELDS:
            value = feature_record.get(field)
            if value is None or value == "":
                continue
            category = _category(field)
            if field == "temperature_change":
                statement = f"Motor temperature changed by {value}°C in the available previous-observation comparison."
            elif field == "battery_change":
                statement = f"Battery level changed by {value}% in the available previous-observation comparison."
            elif field.endswith("_persistence"):
                statement = f"{_readable(field)} is {value} consecutive observation(s)."
            else:
                statement = f"Observed temporal feature {_readable(field)}: {value}."
            item = _item(
                f"TEMP-{field}", category, OBSERVATION, statement,
                "feature_contract", {"field": field, "value": value},
            )
            item.update({"field": field, "value": value})
            temporal.append(item)

        history = observation_quality.get("history") or {}
        if history and history.get("available_prior_observations", 0) < history.get("required_prior_observations", 0):
            temporal.append(_item(
                "TEMP-history-unavailable", "temporal", OBSERVATION,
                "Temporal evidence unavailable: insufficient observation history.",
                "ObservationQuality", history, "INSUFFICIENT",
                limitations=["insufficient observation history"],
            ))

        quality_summary = self._quality_summary(observation_quality)
        missing = self._missing_evidence(
            feature_record, observation_quality, risk_result, diagnosis,
            recommendation, incident, comparison, baseline, fleet_context,
            historical_memory,
        )
        quality_evidence = []
        if observation_quality:
            quality_evidence.append(_item(
                "QUALITY-overall", "observation_quality", OBSERVATION,
                f"Overall observation quality is {quality_summary['overall']}.",
                "observation_quality", quality_summary,
                availability=_quality_status(quality_summary["overall"]),
                limitations=quality_summary["reasons"],
            ))

        engineering, signal_items = self._engineering_evidence(risk_result)
        ml_evidence = self._ml_evidence(risk_result, diagnosis)
        fleet_evidence = self._fleet_evidence(fleet_context)
        history_evidence = self._history_evidence(comparison, baseline, historical_memory)
        pattern_evidence = self._pattern_evidence(telemetry_patterns)
        sampling_evidence = self._sampling_evidence(sampling_analysis)
        contradictions = self._contradictions(risk_result, signal_items, fleet_evidence)

        limitations = self._limitations(
            observation_quality, risk_result, diagnosis, fleet_context,
            historical_memory, incident, missing,
        )
        pattern_limitations = list(telemetry_patterns.get("limitations") or [])
        limitations.extend(
            f"Telemetry pattern analysis: {limitation}"
            for limitation in pattern_limitations
        )
        sampling_limitations = list(sampling_analysis.get("limitations") or [])
        limitations.extend(
            f"Telemetry sampling context: {limitation}"
            for limitation in sampling_limitations
        )
        items = observations + temporal + quality_evidence + engineering + ml_evidence + fleet_evidence + history_evidence + pattern_evidence + sampling_evidence
        evidence_available = any(item["availability"] == "AVAILABLE" for item in items)
        status = (
            "UNAVAILABLE" if not items else
            "DEGRADED" if limitations or any(item["availability"] != "AVAILABLE" for item in items) else
            "AVAILABLE"
        )
        what_changed = [item["statement"] for item in temporal]
        what_unusual = [item["statement"] for item in engineering]
        what_unusual.extend(
            item["statement"] for item in fleet_evidence
            if item["supporting_data"].get("status") in {"OUTLIER", "ELEVATED"}
            or item["supporting_data"].get("pattern") == "peer_wide"
        )
        what_seen_before = [item["statement"] for item in history_evidence]
        what_model_says = [item["statement"] for item in ml_evidence]
        human_action = self._human_action(incident)
        outcome = self._outcome(incident, timeline)
        return _json_safe({
            "incident_id": incident.get("incident_id"),
            "robot_id": feature_record.get("robot_id", incident.get("robot_id")),
            "summary": {
                "status": status,
                "evidence_available": bool(evidence_available),
                "limitations": limitations,
                "what_changed": what_changed,
                "what_pattern_was_observed": [item["statement"] for item in pattern_evidence],
            "what_sampling_context_shows": [item["statement"] for item in sampling_evidence],
                "what_is_unusual": what_unusual,
                "what_we_have_seen_before": what_seen_before,
                "what_the_model_says": what_model_says,
                "what_we_do_not_know": missing,
                "what_happened_after_recommendation": {
                    "human_action": human_action,
                    "outcome": outcome,
                },
            },
            "observations": observations,
            "temporal_evidence": temporal,
            "engineering_evidence": engineering,
            "ml_evidence": ml_evidence,
            "fleet_evidence": fleet_evidence,
            "historical_evidence": history_evidence,
            "pattern_evidence": pattern_evidence,
            "sampling_evidence": sampling_evidence,
            "sampling_analysis": deepcopy(sampling_analysis),
            "pattern_analysis": {
                "status": telemetry_patterns.get("status", "unavailable"),
                "window_size": telemetry_patterns.get("window_size"),
                "observations_analyzed": telemetry_patterns.get("observations_analyzed"),
                "limitations": pattern_limitations,
            },
            "observation_quality": quality_summary,
            "quality_evidence": quality_evidence,
            "contradictions": contradictions,
            "missing_evidence": missing,
            "recommendation": self._recommendation(recommendation),
            "human_action": human_action,
            "outcome": outcome,
            "limitations": limitations,
        })

    @staticmethod
    def _pattern_evidence(pattern_analysis):
        items = []
        patterns = pattern_analysis.get("patterns") or []
        window_size = pattern_analysis.get("window_size")
        for index, pattern in enumerate(patterns):
            name = pattern.get("pattern") or "UNSPECIFIED_PATTERN"
            metrics = deepcopy(pattern.get("metrics") or {})
            observations = deepcopy(pattern.get("observations") or [])
            measurement = (
                metrics.get("measurement")
                or metrics.get("thermal_measurement")
                or metrics.get("field")
            )
            steps = [
                observation.get("time_step")
                for observation in observations
                if isinstance(observation, dict) and observation.get("time_step") is not None
            ]
            statement = pattern.get("description") or f"Observed telemetry pattern {name}."
            items.append(_item(
                f"PATTERN-{name}-{index + 1}",
                pattern.get("domain") or "temporal",
                PATTERN,
                statement,
                "telemetry_pattern_engine",
                {
                    "pattern": name,
                    "affected_telemetry": measurement,
                    "window": {
                        "window_size": window_size,
                        "start_time_step": steps[0] if steps else None,
                        "end_time_step": steps[-1] if steps else None,
                        "observation_count": len(observations),
                    },
                    "observations": observations,
                    "metrics": metrics,
                },
                availability="AVAILABLE",
                limitations=[
                    "Describes an observed telemetry pattern; does not establish diagnosis or cause."
                ],
            ))
        return items

    @staticmethod
    def _sampling_evidence(sampling_analysis):
        items = []
        for index, interval in enumerate(sampling_analysis.get("intervals") or []):
            classification = interval.get("classification", "TIMESTAMP_INTERVAL_OBSERVED")
            description = interval.get("description") or "Observed interval between adjacent telemetry timestamps."
            limitations = []
            if classification == "POSSIBLE_DATA_GAP":
                limitations.append("Possible telemetry gap is not proof that any observation was lost.")
            elif interval.get("sampling_context") == "UNSPECIFIED":
                limitations.append("Expected sampling cadence is unspecified; interval is contextual observation only.")
            items.append(_item(
                f"SAMPLE-interval-{index + 1}", "telemetry_sampling", OBSERVATION,
                description, "telemetry_sampling_context", interval,
                availability="AVAILABLE", limitations=limitations,
            ))
        return items

    @staticmethod
    def _quality_summary(quality):
        groups = quality.get("groups") or {}
        reasons = []
        for group_name, group in groups.items():
            for issue in group.get("issues", []):
                reasons.append({"group": group_name, **deepcopy(issue)})
        return {
            "overall": quality.get("status", "UNAVAILABLE"),
            "thermal": (groups.get("thermal") or {}).get("status", "UNAVAILABLE"),
            "battery": (groups.get("battery") or {}).get("status", "UNAVAILABLE"),
            "workload": (groups.get("workload") or {}).get("status", "UNAVAILABLE"),
            "major_signal_group_limited": quality.get("any_major_group_limited"),
            "history": deepcopy(quality.get("history")),
            "reasons": reasons,
        }

    @staticmethod
    def _engineering_evidence(risk):
        engineering = risk.get("engineering") or (risk.get("fusion") or {}).get("engineering") or {}
        items = []
        for index, signal in enumerate(engineering.get("signals", [])):
            name = signal.get("signal", "engineering signal")
            statement = signal.get("message") or f"Engineering signal detected: {name}."
            item = _item(
                f"ENG-{index}-{name}", "engineering", ENGINEERING_SIGNAL,
                statement, "ReliabilitySignal", signal,
            )
            item.update(signal)
            item["type"] = ENGINEERING_SIGNAL
            items.append(item)
        return items, items

    @staticmethod
    def _ml_evidence(risk, diagnosis):
        evidence = []
        available = bool(risk.get("prediction_available", risk.get("probability") is not None))
        if available:
            probability = risk.get("probability")
            statement = (
                f"Model estimated failure probability of {probability:.2f}."
                if isinstance(probability, (int, float)) else
                "Model prediction is available; probability was not provided."
            )
            evidence.append(_item(
                "ML-risk", "ML", ML_INFERENCE, statement, "PredictionEngine",
                {"probability": probability, "prediction": risk.get("model_prediction"),
                 "model_prediction": risk.get("model_prediction"),
                 "operational_prediction": risk.get("prediction"),
                 "predicted_risk": risk.get("fused_risk")},
            ))
        else:
            evidence.append(_item(
                "ML-risk-unavailable", "ML", ML_INFERENCE,
                "ML inference unavailable.", "PredictionEngine", {}, "UNAVAILABLE",
                limitations=[risk.get("unavailable_reason") or "prediction unavailable"],
            ))
        if diagnosis:
            failure_type = diagnosis.get("failure_type")
            cause = diagnosis.get("probable_cause")
            statement = "Diagnosis inference unavailable."
            if failure_type or cause:
                statement = "Diagnosis inference: " + "; ".join(
                    item for item in (
                        f"possible {failure_type}" if failure_type else None,
                        cause,
                    ) if item
                ) + "."
            evidence.append(_item(
                "ML-diagnosis", "ML", ML_INFERENCE, statement,
                "DiagnosisEngine", diagnosis,
                confidence=diagnosis.get("confidence"),
            ))
        else:
            evidence.append(_item(
                "ML-diagnosis-unavailable", "ML", ML_INFERENCE,
                "Diagnosis unavailable.", "DiagnosisEngine", {}, "UNAVAILABLE",
                limitations=["diagnosis not provided by the existing diagnosis system"],
            ))
        return evidence

    @staticmethod
    def _fleet_evidence(fleet_context):
        evidence = []
        for metric, data in (fleet_context.get("metrics") or {}).items():
            statement = data.get("interpretation") or f"Peer comparison for {metric} is unavailable."
            item = _item(
                f"FLEET-{metric}", "fleet", FLEET_COMPARISON,
                statement, "FleetBaseline", data,
                availability="AVAILABLE" if data.get("status") != "INSUFFICIENT_DATA" else "INSUFFICIENT",
                limitations=data.get("limitations", []),
            )
            item.update(data)
            item["evidence_type"] = FLEET_COMPARISON
            item["type"] = FLEET_COMPARISON
            evidence.append(item)
        if not evidence or fleet_context.get("status") != "AVAILABLE":
            evidence.append(_item(
                "FLEET-unavailable", "fleet", FLEET_COMPARISON,
                fleet_context.get("message") or "Fleet comparison unavailable.",
                "FleetBaseline", fleet_context,
                "INSUFFICIENT", limitations=fleet_context.get("limitations", []),
            ))
        return evidence

    @staticmethod
    def _history_evidence(comparison, baseline, memory):
        evidence = []
        for source, result in (("ComparisonEngine", comparison), ("BaselineEngine", baseline)):
            for metric, value in (result.get("metrics") or {}).items():
                evidence.append(_item(
                    f"HIST-{source}-{metric}", "history", HISTORICAL_COMPARISON,
                    f"{_readable(metric)} from {source}: {value}.", source,
                    {"metric": metric, "value": value, "status": result.get("status")},
                ))
        incidents = memory.get("incidents") or []
        for incident in incidents:
            incident_id = incident.get("incident_id", "unknown")
            reasons = incident.get("similarity_reasons") or []
            reason_text = ", ".join(reasons) if reasons else "available incident context"
            evidence.append(_item(
                f"HIST-{incident_id}", "history", HISTORICAL_COMPARISON,
                f"Incident {incident_id} matched on {reason_text}.",
                "ReliabilityMemory", incident,
            ))
        if not evidence:
            evidence.append(_item(
                "HIST-unavailable", "history", HISTORICAL_COMPARISON,
                memory.get("message") or "Historical comparison unavailable.",
                "ReliabilityMemory", memory, "UNAVAILABLE",
                limitations=["no matching historical incident or comparison was available"],
            ))
        return evidence

    @staticmethod
    def _contradictions(risk, engineering, fleet):
        contradictions = []
        model_prediction = risk.get("model_prediction")
        critical = [
            item for item in engineering
            if item.get("supporting_data", {}).get("severity") == "critical"
        ]
        if model_prediction == 0 and critical:
            contradictions.append({
                "contradiction_id": "ml-vs-critical-engineering",
                "sources": ["PredictionEngine", "ReliabilitySignal"],
                "statement": "ML inference and a critical engineering signal disagree.",
                "supporting_evidence_ids": ["ML-risk"] + [item["evidence_id"] for item in critical],
                "resolved": False,
            })
        thermal_outliers = [
            item for item in fleet
            if item.get("supporting_data", {}).get("metric") in {
                "motor_temperature", "thermal_rise", "ambient_temperature",
            }
            and item.get("supporting_data", {}).get("status") == "OUTLIER"
        ]
        thermal_critical = [
            item for item in engineering
            if "thermal" in str(item.get("supporting_data", {}).get("signal", ""))
            or "motor_temperature" in str(item.get("supporting_data", {}).get("signal", ""))
        ]
        if thermal_outliers and not thermal_critical:
            contradictions.append({
                "contradiction_id": "fleet-thermal-vs-engineering", 
                "sources": ["FleetBaseline", "ReliabilitySignal"],
                "statement": "Fleet comparison marks a thermal metric as an outlier while no critical thermal engineering signal is present.",
                "supporting_evidence_ids": [item["evidence_id"] for item in thermal_outliers],
                "resolved": False,
            })
        return contradictions

    @staticmethod
    def _missing_evidence(feature_record, quality, risk, diagnosis, recommendation,
                          incident, comparison, baseline, fleet, memory):
        missing = []
        if not quality or quality.get("status") in (None, "UNAVAILABLE"):
            missing.append("observation quality unavailable")
        history = quality.get("history") or {}
        if history and history.get("available_prior_observations", 0) < history.get("required_prior_observations", 0):
            missing.append("insufficient temporal history")
        elif any(feature_record.get(field) is None for field in TEMPORAL_FIELDS):
            missing.append("one or more temporal features are unavailable")
        if not risk.get("prediction_available", risk.get("probability") is not None):
            missing.append(risk.get("unavailable_reason") or "ML prediction unavailable")
        if diagnosis is None:
            missing.append("Diagnosis unavailable")
        if fleet.get("status") != "AVAILABLE":
            missing.append(fleet.get("message") or "comparable peer evidence unavailable")
        if memory.get("status") != "AVAILABLE":
            missing.append(memory.get("message") or "historical memory unavailable")
        if not comparison.get("metrics") and not baseline.get("metrics"):
            missing.append("historical comparison unavailable")
        groups = quality.get("groups") or {}
        for name, group in groups.items():
            if group.get("status") != "AVAILABLE":
                missing.append(f"{name} evidence {group.get('status', 'unavailable').lower()}")
        if not incident.get("actions"):
            missing.append("no recorded human action")
        if not incident.get("outcome"):
            missing.append("outcome pending")
        if not recommendation.get("recommendation"):
            missing.append("recommendation unavailable")
        return list(dict.fromkeys(missing))

    @staticmethod
    def _limitations(quality, risk, diagnosis, fleet, memory, incident, missing):
        limitations = list(missing)
        for group_name, group in (quality.get("groups") or {}).items():
            if group.get("status") != "AVAILABLE":
                limitations.extend(
                    f"{group_name}: {issue.get('check', 'quality limitation')}"
                    for issue in group.get("issues", [])
                )
        limitations.extend(fleet.get("limitations", []))
        if risk.get("confidence_limited"):
            limitations.append("risk inference confidence is limited by the existing quality assessment")
        if diagnosis is None:
            limitations.append("diagnosis is not available from the existing diagnosis system")
        if memory.get("status") != "AVAILABLE":
            limitations.append(memory.get("message") or "historical memory unavailable")
        if not incident.get("outcome"):
            limitations.append("outcome pending")
        return list(dict.fromkeys(item for item in limitations if item))

    @staticmethod
    def _recommendation(recommendation):
        return {
            "status": "AVAILABLE" if recommendation.get("recommendation") else "UNAVAILABLE",
            "text": recommendation.get("recommendation"),
            "reason": recommendation.get("probable_cause"),
            "severity": recommendation.get("risk_level"),
            "priority": recommendation.get("risk_level"),
        }

    @staticmethod
    def _human_action(incident):
        items = deepcopy(incident.get("actions") or [])
        return {"status": "RECORDED" if items else "PENDING", "items": items}

    @staticmethod
    def _outcome(incident, timeline):
        events = timeline.get("events", [])
        recovery_events = [event for event in events if event.get("event_type") == "recovery"]
        details = deepcopy(incident.get("outcome"))
        resolved = bool(incident.get("status") == "CLOSED" and details)
        return {
            "status": "RESOLVED" if resolved else "OUTCOME_PENDING",
            "resolved": resolved,
            "details": details,
            "failure_events": [event for event in events if event.get("event_type") == "failure"],
            "recovery_events": recovery_events,
        }
