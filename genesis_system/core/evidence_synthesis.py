"""Deterministic organization of existing Genesis evidence and decisions."""

from copy import deepcopy
import math
from numbers import Real

from feature_contract import DEPLOYABLE_FEATURES, RAW_FEATURES
from observation_security import ObservationSecurity
from evidence_contract import Evidence, EvidenceCategory


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
        baseline_visibility=None,
        fleet_context=None,
        historical_memory=None,
        timeline=None,
        telemetry_patterns=None,
        sampling_analysis=None,
        observation_security=None,
        evidence_items=None,
        historical_records=None,
    ):
        observation_quality = deepcopy(observation_quality or {})
        risk_result = risk_result or {}
        diagnosis = diagnosis or None
        recommendation = recommendation or {}
        incident = incident.summary() if hasattr(incident, "summary") else (incident or {})
        comparison = comparison or {}
        baseline = baseline or {}
        baseline_visibility = baseline_visibility or {
            "status": (
                "AVAILABLE" if baseline.get("status") == "baseline_available"
                else "INSUFFICIENT"
            ),
            "reason": baseline.get("message"),
            "eligible_records": baseline.get("records_used", 0),
            "required_records": None,
            "observed_records": None,
        }
        fleet_context = fleet_context or {}
        historical_memory = historical_memory or {
            "status": "UNAVAILABLE", "match_count": 0, "incidents": [],
            "message": "historical memory unavailable",
        }
        timeline = timeline or {}
        telemetry_patterns = telemetry_patterns or {}
        sampling_analysis = sampling_analysis or {}
        observation_security = observation_security or ObservationSecurity().assess(
            feature_record,
            source_time_step=feature_record.get("time_step"),
        )

        evidence_items = list(evidence_items or [])
        contract_evidence = self._contract_evidence(evidence_items)

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
                {"field": field, "value": value, "time_step": feature_record.get("time_step"),
                 "temporal_scope": "SINGLE_OBSERVATION"},
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
                "feature_contract", {"field": field, "value": value,
                                     "time_step": feature_record.get("time_step"),
                                     "temporal_scope": "DERIVED_FEATURE_WINDOW_NOT_EXPOSED"},
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
            historical_memory, baseline_visibility,
        )
        quality_evidence = []
        security_evidence = self._security_evidence(observation_security)
        if observation_quality:
            quality_evidence.append(_item(
                "QUALITY-overall", "observation_quality", OBSERVATION,
                f"Overall observation quality is {quality_summary['overall']}.",
                "observation_quality", quality_summary,
                availability=_quality_status(quality_summary["overall"]),
                limitations=quality_summary["reasons"],
            ))

        engineering, signal_items = self._engineering_evidence(risk_result)
        # This is the evaluation step, not proof that a signal's underlying
        # sensor was sampled at this exact instant. Keep the distinction explicit.
        for item in signal_items:
            data = item.setdefault("supporting_data", {})
            data.setdefault("evaluation_time_step", feature_record.get("time_step"))
            data.setdefault("measurement_time_step", None)
        ml_evidence = self._ml_evidence(risk_result, diagnosis)
        fleet_evidence = self._fleet_evidence(fleet_context)
        history_evidence = self._history_evidence(
            comparison, baseline, historical_memory, baseline_visibility
        )
        pattern_evidence = self._pattern_evidence(telemetry_patterns)
        sampling_evidence = self._sampling_evidence(sampling_analysis)
        contradictions = self._contradictions(risk_result, signal_items, fleet_evidence)

        limitations = self._limitations(
            observation_quality, risk_result, diagnosis, fleet_context,
            historical_memory, incident, missing, baseline_visibility,
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
        items = (
            observations
            + temporal
            + quality_evidence
            + security_evidence
            + contract_evidence
            + engineering
            + ml_evidence
            + fleet_evidence
            + history_evidence
            + pattern_evidence
            + sampling_evidence
        )
        evidence_lineage = self._build_evidence_lineage(
            items, contradictions, feature_record=feature_record,
            historical_records=historical_records or [],
        )
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
            "contract_evidence": contract_evidence,
            "temporal_evidence": temporal,
            "engineering_evidence": engineering,
            "ml_evidence": ml_evidence,
            "fleet_evidence": fleet_evidence,
            "historical_evidence": history_evidence,
            "baseline_visibility": deepcopy(baseline_visibility),
            "historical_comparison": {
                "status": "AVAILABLE" if (
                    (comparison.get("metrics") or {}) or (baseline.get("metrics") or {})
                ) else "UNAVAILABLE",
                "comparison_metrics": deepcopy(comparison.get("metrics") or {}),
                "baseline": deepcopy(baseline_visibility),
                "message": None if (
                    (comparison.get("metrics") or {}) or (baseline.get("metrics") or {})
                ) else "Historical comparison unavailable.",
            },
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
            "security_evidence": security_evidence,
            "observation_security": deepcopy(observation_security),
            "contradictions": contradictions,
            "evidence_lineage": evidence_lineage,
            "missing_evidence": missing,
            "recommendation": self._recommendation(recommendation),
            "human_action": human_action,
            "outcome": outcome,
            "limitations": limitations,
        })

    @staticmethod
    def _contract_evidence(evidence_items):
        """Convert shared Evidence objects into Genesis synthesis records."""
        items = []
        for index, evidence in enumerate(evidence_items):
            if not isinstance(evidence, Evidence):
                raise TypeError("evidence_items must contain Evidence objects.")

            metadata = deepcopy(evidence.metadata)
            context = deepcopy(evidence.context)
            availability = metadata.pop("availability", "AVAILABLE")
            statement = metadata.pop("statement", None) or f"{evidence.name}: {evidence.value}."
            supporting_data = {"value": deepcopy(evidence.value), "context": context, **metadata}

            items.append(_item(
                f"CONTRACT-{index + 1}-{evidence.category.value}",
                evidence.category.value,
                evidence.category.value.upper(),
                statement,
                evidence.source,
                supporting_data,
                availability=availability,
                confidence=evidence.confidence,
                limitations=list(evidence.limitations),
            ))
        return items

    @staticmethod
    def _security_evidence(security):
        status = security.get("status", "UNKNOWN")
        source = security.get("source") or {}
        statement = (
            f"Observation security status is {status}; source authentication, integrity, "
            f"authorization, and freshness are assessed separately."
        )
        return [_item(
            "SECURITY-observation",
            "observation_security",
            OBSERVATION,
            statement,
            "observation_security",
            {
                "status": status,
                "source": source,
                "authentication": security.get("authentication"),
                "integrity": security.get("integrity"),
                "authorization": security.get("authorization"),
                "freshness": security.get("freshness"),
            },
            availability="AVAILABLE" if status in {"TRUSTED", "DEGRADED"} else "DEGRADED",
            limitations=security.get("limitations") or [],
        )]

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
    def _build_evidence_lineage(items, contradictions, feature_record=None, historical_records=None):
        """Build an explicit, conservative evidence graph from known references.

        Direct engineering-to-observation links are emitted only when the signal
        name identifies a telemetry field and its value exactly matches the
        observation evidence value. This is a field/value match, not causation.
        Other edges require IDs explicitly supplied by the producing subsystem.
        """
        nodes = []
        edges = []
        unresolved = []
        temporal_order_warnings = []
        by_id = {item.get("evidence_id"): item for item in items if item.get("evidence_id")}
        feature_record = feature_record or {}
        current_robot = feature_record.get("robot_id")
        historical_records = [
            deepcopy(record) for record in (historical_records or [])
            if isinstance(record, dict)
            and record.get("robot_id") == current_robot
        ]

        def numeric_step(value):
            # Do not parse timestamp strings or coerce arbitrary values: their
            # clock basis and semantics may differ.
            return float(value) if isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value)) else None

        def temporal_metadata(item):
            data = item.get("supporting_data") or {}
            window = data.get("window") if isinstance(data.get("window"), dict) else {}
            scope = data.get("temporal_scope") or ("OBSERVED_WINDOW" if window else "POINT_OR_UNKNOWN")
            if scope == "DERIVED_FEATURE_WINDOW_NOT_EXPOSED":
                return {
                    "start_time_step": None,
                    "end_time_step": None,
                    "evaluation_time_step": data.get("time_step"),
                    "scope": scope,
                }
            start = window.get("start_time_step")
            end = window.get("end_time_step")
            if end is None:
                end = data.get("time_step", data.get("evaluation_time_step"))
            if start is None:
                start = data.get("time_step", data.get("evaluation_time_step"))
            return {
                "start_time_step": start,
                "end_time_step": end,
                "scope": scope,
            }

        def temporal_order(source_item, target_item):
            source = temporal_metadata(source_item)
            target = temporal_metadata(target_item)
            source_end = numeric_step(source.get("end_time_step"))
            target_end = numeric_step(target.get("end_time_step"))
            if source_end is None or target_end is None:
                return {"status": "TIME_ORDER_UNAVAILABLE", "source_end_time_step": source.get("end_time_step"),
                        "target_end_time_step": target.get("end_time_step")}
            if source_end > target_end:
                return {"status": "UPSTREAM_AFTER_DEPENDENT", "source_end_time_step": source_end,
                        "target_end_time_step": target_end}
            return {"status": "NOT_AFTER_DEPENDENT", "source_end_time_step": source_end,
                    "target_end_time_step": target_end}

        for item in items:
            evidence_id = item.get("evidence_id")
            if not evidence_id:
                continue
            nodes.append({
                "evidence_id": evidence_id,
                "category": item.get("category"),
                "evidence_type": item.get("evidence_type") or item.get("type"),
                "source": item.get("source"),
                "statement": item.get("statement"),
                "temporal": temporal_metadata(item),
            })

        # The signal-to-field vocabulary is deliberately finite and inspectable.
        telemetry_fields = (
            "motor_temperature", "ambient_temperature", "thermal_rise",
            "battery_level", "battery_voltage", "battery_current",
            "battery_temperature", "voltage_drop", "workload",
            "power_consumption", "robot_state",
        )
        for item in items:
            evidence_id = item.get("evidence_id")
            if not evidence_id:
                continue
            declared = item.get("supporting_evidence_ids") or item.get("input_evidence_ids")
            if not declared:
                data = item.get("supporting_data") or {}
                declared = data.get("supporting_evidence_ids") or data.get("input_evidence_ids")
            if not declared and item.get("evidence_type") == ENGINEERING_SIGNAL:
                signal_name = str(item.get("signal") or "").lower()
                signal_value = item.get("value")
                matched_field = next((field for field in telemetry_fields if field in signal_name), None)
                if matched_field and signal_value is not None:
                    observation_id = f"OBS-{matched_field}"
                    observation = by_id.get(observation_id)
                    if observation is not None and observation.get("value") == signal_value:
                        declared = [observation_id]
                        item["input_evidence_ids"] = list(declared)
                        item["lineage_relationship"] = "FIELD_VALUE_MATCH_NOT_CAUSATION"
                        item["lineage_basis"] = "Genesis deterministic signal-name/field and value equality match"
            if not declared:
                continue
            for ref in declared:
                ref_id = ref if isinstance(ref, str) else (ref.get("evidence_id") if isinstance(ref, dict) else None)
                if not ref_id or ref_id not in by_id:
                    unresolved.append({"dependent_evidence_id": evidence_id, "upstream_reference": ref, "status": "UNRESOLVED_REFERENCE"})
                    continue
                edge = {
                    "from_evidence_id": ref_id,
                    "to_evidence_id": evidence_id,
                    "relationship": item.get("lineage_relationship") or "EXPLICIT_UPSTREAM_REFERENCE",
                    "basis": item.get("lineage_basis") or "Declared by evidence-producing subsystem",
                }
                edge["temporal_order"] = temporal_order(by_id[ref_id], item)
                if edge["temporal_order"]["status"] == "UPSTREAM_AFTER_DEPENDENT":
                    temporal_order_warnings.append({
                        "from_evidence_id": ref_id,
                        "to_evidence_id": evidence_id,
                        **edge["temporal_order"],
                        "status": "TEMPORAL_ORDER_CONFLICT",
                    })
                edges.append(edge)

        # Derived features declare their actual source rows using the same
        # window/lag conventions as genesis_system.robotics.feature_contract.
        # These are computational-input links, not causal claims.
        feature_specs = {
            "temperature_change": ("motor_temperature", "delta", 1),
            "battery_change": ("battery_level", "delta", 1),
            "battery_voltage_change": ("battery_voltage", "delta", 1),
            "battery_current_change": ("battery_current", "delta", 1),
            "battery_temperature_change": ("battery_temperature", "delta", 1),
            "power_change": ("power_consumption", "delta", 1),
            "temperature_rate_3": ("motor_temperature", "lag", 3),
            "temperature_rate_5": ("motor_temperature", "lag", 4),
            "thermal_rise_rate_3": ("thermal_rise", "lag", 3),
            "battery_drop_rate_3": ("battery_level", "lag", 3),
            "battery_voltage_drop_rate_3": ("battery_voltage", "lag", 3),
            "battery_temperature_rate_3": ("battery_temperature", "lag", 3),
            "power_rate_3": ("power_consumption", "lag", 3),
            "temperature_avg_3": ("motor_temperature", "window", 3),
            "temperature_avg_5": ("motor_temperature", "window", 5),
            "thermal_rise_max_3": ("thermal_rise", "window", 3),
            "thermal_rise_max_5": ("thermal_rise", "window", 5),
            "thermal_rise_avg_3": ("thermal_rise", "window", 3),
            "thermal_rise_avg_5": ("thermal_rise", "window", 5),
            "battery_decline_3": ("battery_level", "window", 3),
            "battery_decline_5": ("battery_level", "window", 5),
            "battery_voltage_decline_3": ("battery_voltage", "window", 3),
            "battery_current_change_3": ("battery_current", "window", 3),
            "thermal_elevated_persistence": ("thermal_rise", "persistence_high", 20),
            "low_battery_persistence": ("battery_level", "persistence_low", 35),
            "temperature_acceleration": ("motor_temperature", "acceleration", 3),
        }

        def row_field_value(row, field):
            if field == "thermal_rise":
                if row.get("thermal_rise") is not None:
                    return row.get("thermal_rise")
                motor, ambient = row.get("motor_temperature"), row.get("ambient_temperature")
                if isinstance(motor, Real) and isinstance(ambient, Real):
                    return motor - ambient
                return None
            return row.get(field)

        def historical_indexes(field, mode, count, feature_value):
            n = len(historical_records)
            if mode == "delta":
                return [n - 1] if n >= 1 else []
            if mode == "lag":
                return [n - count] if n >= count else []
            if mode == "window":
                return list(range(max(0, n - count + 1), n)) if n >= count - 1 else []
            if mode == "acceleration":
                return list(range(n - 2, n)) if n >= 2 else []
            if mode in {"persistence_high", "persistence_low"}:
                try:
                    needed = max(0, int(feature_value) - 1)
                except (TypeError, ValueError):
                    return []
                indexes = []
                for index in range(n - 1, max(-1, n - needed - 1), -1):
                    value = row_field_value(historical_records[index], field)
                    if value is None:
                        break
                    matches = value >= count if mode == "persistence_high" else value <= count
                    if not matches:
                        break
                    indexes.append(index)
                return list(reversed(indexes))
            return []

        def historical_node(row, index, fields, feature_id):
            robot = row.get("robot_id", feature_record.get("robot_id", "unknown"))
            step = row.get("time_step")
            # Index is included so duplicate/missing time steps cannot silently merge.
            node_id = f"INPUT-ROW-{robot}-i{index}-t{step if step is not None else 'unknown'}"
            if node_id not in by_id:
                supporting = {field: row_field_value(row, field) for field in fields}
                if "thermal_rise" in fields:
                    supporting["motor_temperature"] = row.get("motor_temperature")
                    supporting["ambient_temperature"] = row.get("ambient_temperature")
                node_item = {
                    "evidence_id": node_id,
                    "category": "derived_feature_input",
                    "evidence_type": OBSERVATION,
                    "source": "historical_records",
                    "statement": f"Historical input observation at time step {step}.",
                    "supporting_data": {"time_step": step, "robot_id": robot, "input_fields": list(fields), "values": supporting},
                }
                by_id[node_id] = node_item
                nodes.append({
                    "evidence_id": node_id, "category": node_item["category"],
                    "evidence_type": OBSERVATION, "source": node_item["source"],
                    "statement": node_item["statement"],
                    "temporal": {"start_time_step": step, "end_time_step": step,
                                 "scope": "SINGLE_OBSERVATION" if step is not None else "TIME_STEP_NOT_EXPOSED"},
                })
            return node_id

        for item in items:
            if item.get("evidence_type") != OBSERVATION or not str(item.get("evidence_id", "")).startswith("TEMP-"):
                continue
            feature = (item.get("supporting_data") or {}).get("field")
            spec = feature_specs.get(feature)
            if not spec:
                continue
            base_field, mode, count = spec
            indexes = historical_indexes(base_field, mode, count, (item.get("supporting_data") or {}).get("value"))
            if mode in {"delta", "lag", "window", "acceleration"} and not indexes:
                continue
            fields = ["motor_temperature", "ambient_temperature"] if base_field == "thermal_rise" else [base_field]
            # Current record is always an input for any emitted derived feature.
            current_fields = fields if base_field != "thermal_rise" else ["motor_temperature", "ambient_temperature"]
            current_refs = [f"OBS-{field}" for field in current_fields if f"OBS-{field}" in by_id]
            selected_steps = [historical_records[index].get("time_step") for index in indexes]
            selected_steps.append(feature_record.get("time_step"))
            data = item.setdefault("supporting_data", {})
            data["input_observation_ids"] = list(current_refs)
            data["input_fields"] = list(current_fields)
            data["temporal_scope"] = "DERIVED_FEATURE_WINDOW_EXPOSED"
            data["window"] = {
                "start_time_step": selected_steps[0] if selected_steps else None,
                "end_time_step": selected_steps[-1] if selected_steps else None,
                "observation_count": len(selected_steps),
                "selection_method": mode,
            }
            for node in nodes:
                if node.get("evidence_id") == item["evidence_id"]:
                    node["temporal"] = temporal_metadata(item)
                    break
            for ref_id in current_refs:
                edge = {
                    "from_evidence_id": ref_id,
                    "to_evidence_id": item["evidence_id"],
                    "relationship": "INPUT_TO_DERIVED_FEATURE",
                    "basis": f"Feature contract uses current observation field(s) {', '.join(current_fields)} to compute {feature}; input dependency, not causation.",
                    "temporal_order": temporal_order(by_id[ref_id], item),
                }
                edges.append(edge)
            for index in indexes:
                row = historical_records[index]
                # Persistence may stop at a threshold boundary; only rows selected
                # by the feature's observed count are included.
                ref_id = historical_node(row, index, fields, item["evidence_id"])
                edge = {
                    "from_evidence_id": ref_id,
                    "to_evidence_id": item["evidence_id"],
                    "relationship": "INPUT_TO_DERIVED_FEATURE",
                    "basis": f"Feature contract source selection ({mode}, count={count}) for {feature}; computational input, not causation.",
                    "temporal_order": temporal_order(by_id[ref_id], item),
                }
                if edge["temporal_order"]["status"] == "UPSTREAM_AFTER_DEPENDENT":
                    temporal_order_warnings.append({
                        "from_evidence_id": ref_id, "to_evidence_id": item["evidence_id"],
                        **edge["temporal_order"], "status": "TEMPORAL_ORDER_CONFLICT",
                    })
                edges.append(edge)

        # thermal_rise is a direct feature-contract calculation from the
        # current motor and ambient temperatures. Preserve that exact formula
        # dependency separately from any later temporal trend.
        thermal_rise = by_id.get("OBS-thermal_rise")
        motor_observation = by_id.get("OBS-motor_temperature")
        ambient_observation = by_id.get("OBS-ambient_temperature")
        if thermal_rise and motor_observation and ambient_observation:
            motor_value = (motor_observation.get("supporting_data") or {}).get("value")
            ambient_value = (ambient_observation.get("supporting_data") or {}).get("value")
            rise_value = (thermal_rise.get("supporting_data") or {}).get("value")
            if (isinstance(motor_value, Real) and isinstance(ambient_value, Real)
                    and isinstance(rise_value, Real) and round(motor_value - ambient_value, 2) == round(rise_value, 2)):
                for source_id, field in (("OBS-motor_temperature", "motor_temperature"),
                                         ("OBS-ambient_temperature", "ambient_temperature")):
                    edges.append({
                        "from_evidence_id": source_id,
                        "to_evidence_id": "OBS-thermal_rise",
                        "relationship": "FORMULA_INPUT_TO_DERIVED_FEATURE",
                        "basis": f"Feature contract computes thermal_rise as motor_temperature minus ambient_temperature; exact formula dependency for {field}, not causation.",
                        "temporal_order": temporal_order(by_id[source_id], thermal_rise),
                    })

        # Pattern evidence embeds the exact telemetry rows used by its window.
        # Represent those rows as traceable graph nodes and link them to the
        # pattern they are members of. These are membership/support links, not
        # causal claims. Where a current field-level observation matches a row
        # at the same numeric time step and has the same value, connect it to
        # that row using an explicitly limited field/value/time association.
        window_nodes = {}
        for item in items:
            if item.get("evidence_type") != PATTERN:
                continue
            pattern_id = item.get("evidence_id")
            data = item.get("supporting_data") or {}
            window = data.get("window") if isinstance(data.get("window"), dict) else {}
            rows = data.get("observations")
            if not isinstance(rows, list):
                continue
            for row_index, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                step = row.get("time_step")
                # The pattern's embedded row is the source of this node. If a
                # step is absent, keep the row distinct instead of guessing.
                window_id = f"WINDOW-OBS-t{step}" if step is not None else f"WINDOW-OBS-{pattern_id}-{row_index + 1}"
                existing = window_nodes.get(window_id)
                if existing is not None and existing["supporting_data"] != row:
                    # A reused step with a different payload is not silently
                    # merged; give the second payload a distinct stable ID.
                    window_id = f"{window_id}-{row_index + 1}-{pattern_id}"
                if window_id not in window_nodes:
                    window_item = {
                        "evidence_id": window_id,
                        "category": "telemetry_window_observation",
                        "evidence_type": OBSERVATION,
                        "source": item.get("source") or "telemetry_pattern_engine",
                        "statement": f"Telemetry window observation at time step {step}." if step is not None else f"Telemetry window observation {row_index + 1}; time step not exposed.",
                        "supporting_data": deepcopy(row),
                    }
                    window_nodes[window_id] = window_item
                    nodes.append({
                        "evidence_id": window_id,
                        "category": window_item["category"],
                        "evidence_type": OBSERVATION,
                        "source": window_item["source"],
                        "statement": window_item["statement"],
                        "temporal": {
                            "start_time_step": step,
                            "end_time_step": step,
                            "scope": "SINGLE_OBSERVATION" if step is not None else "TIME_STEP_NOT_EXPOSED",
                        },
                    })
                    by_id[window_id] = window_item
                window_edge = {
                    "from_evidence_id": window_id,
                    "to_evidence_id": pattern_id,
                    "relationship": "OBSERVED_IN_PATTERN_WINDOW",
                    "basis": "The pattern producer explicitly embedded this row in supporting_data.observations; window membership is not causation.",
                    "temporal_order": temporal_order(by_id[window_id], item),
                }
                if window_edge["temporal_order"]["status"] == "UPSTREAM_AFTER_DEPENDENT":
                    temporal_order_warnings.append({
                        "from_evidence_id": window_id,
                        "to_evidence_id": pattern_id,
                        **window_edge["temporal_order"],
                        "status": "TEMPORAL_ORDER_CONFLICT",
                    })
                edges.append(window_edge)
                # Join the current field-level observations to a source-window
                # row only on exact field/value and numeric time-step equality.
                for field, value in row.items():
                    if field == "time_step":
                        continue
                    observation = by_id.get(f"OBS-{field}")
                    if not observation:
                        continue
                    observation_data = observation.get("supporting_data") or {}
                    if (observation_data.get("time_step") == step
                            and observation_data.get("value") == value):
                        edges.append({
                            "from_evidence_id": f"OBS-{field}",
                            "to_evidence_id": window_id,
                            "relationship": "FIELD_VALUE_MATCH_AT_TIME_STEP",
                            "basis": "Exact field/value and time-step match between the current observation evidence and a row embedded in the pattern window; not causation.",
                            "temporal_order": temporal_order(observation, by_id[window_id]),
                        })

        # Contradiction objects explicitly declare their supporting evidence IDs.
        for contradiction in contradictions or []:
            contradiction_id = contradiction.get("contradiction_id")
            if not contradiction_id:
                continue
            nodes.append({
                "evidence_id": contradiction_id,
                "category": "contradiction",
                "evidence_type": "CONTRADICTION",
                "source": ", ".join(contradiction.get("sources") or []) or None,
                "statement": contradiction.get("statement"),
                "temporal": {"start_time_step": None, "end_time_step": None, "scope": "NOT_EXPOSED"},
            })
            for ref_id in contradiction.get("supporting_evidence_ids") or []:
                if ref_id in by_id:
                    edge = {
                        "from_evidence_id": ref_id,
                        "to_evidence_id": contradiction_id,
                        "relationship": "SUPPORTS_CONTRADICTION",
                        "basis": "Explicit supporting_evidence_ids on contradiction record",
                    }
                    edge["temporal_order"] = temporal_order(by_id[ref_id], {})
                    if edge["temporal_order"]["status"] == "UPSTREAM_AFTER_DEPENDENT":
                        temporal_order_warnings.append({
                            "from_evidence_id": ref_id,
                            "to_evidence_id": contradiction_id,
                            **edge["temporal_order"],
                            "status": "TEMPORAL_ORDER_CONFLICT",
                        })
                    edges.append(edge)
                else:
                    unresolved.append({"dependent_evidence_id": contradiction_id, "upstream_reference": ref_id, "status": "UNRESOLVED_REFERENCE"})

        incident_nodes = {
            evidence_id
            for edge in edges
            for evidence_id in (edge.get("from_evidence_id"), edge.get("to_evidence_id"))
            if evidence_id
        }
        item_ids = [item.get("evidence_id") for item in items if item.get("evidence_id")]
        unlinked = [item_id for item_id in item_ids if item_id not in incident_nodes]
        return {
            "schema_version": "1.2",
            "status": "PARTIAL" if unlinked or unresolved else "LINKED",
            "nodes": nodes,
            "edges": edges,
            "unlinked_evidence_ids": unlinked,
            "unresolved_references": unresolved,
            "temporal_order_warnings": temporal_order_warnings,
            "limitations": [
                "A field/value match establishes a traceable association only, not causation.",
                "No edge is inferred when the producing subsystem does not expose a reference or a conservative direct match is unavailable.",
                "Pattern-window membership links reflect embedded source rows, not causal contribution or proof that a row is valid.",
            ],
            "counts": {
                "nodes": len(nodes),
                "evidence_items": len(item_ids),
                "window_observation_nodes": len(window_nodes),
                "edges": len(edges),
                "unlinked_evidence": len(unlinked),
                "unresolved_references": len(unresolved),
                "temporal_order_warnings": len(temporal_order_warnings),
            },
        }

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
    def _history_evidence(comparison, baseline, memory, baseline_visibility=None):
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
        baseline_visibility = baseline_visibility or {}
        baseline_status = baseline_visibility.get("status")
        baseline_reason = baseline_visibility.get("reason")
        if baseline_status:
            status_text = {
                "AVAILABLE": "available",
                "INSUFFICIENT": "insufficient",
                "ELIGIBILITY_UNKNOWN": "unavailable because eligibility is unknown",
            }.get(baseline_status, baseline_status.lower())
            details = deepcopy(baseline_visibility)
            details["metrics"] = deepcopy(baseline.get("metrics") or {})
            evidence.append(_item(
                "HIST-baseline-status", "history", HISTORICAL_COMPARISON,
                f"Historical baseline is {status_text}."
                + (f" {baseline_reason}" if baseline_reason else ""),
                "BaselineEngine", details,
                "AVAILABLE" if baseline_status == "AVAILABLE" else "INSUFFICIENT",
                limitations=[] if baseline_status == "AVAILABLE" else [baseline_reason],
            ))
        if not (comparison.get("metrics") or baseline.get("metrics")):
            evidence.append(_item(
                "HIST-comparison-unavailable", "history", HISTORICAL_COMPARISON,
                "Historical comparison unavailable.",
                "ComparisonEngine", {"comparison_status": "UNAVAILABLE"}, "UNAVAILABLE",
                limitations=["no historical comparison metrics were available"],
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
                          incident, comparison, baseline, fleet, memory,
                          baseline_visibility=None):
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
        baseline_visibility = baseline_visibility or {}
        if baseline_visibility.get("status") in {"INSUFFICIENT", "ELIGIBILITY_UNKNOWN"}:
            missing.append(
                "Baseline " + baseline_visibility.get("status", "unavailable").lower()
                + ": " + (baseline_visibility.get("reason") or "baseline evidence unavailable")
            )
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
    def _limitations(quality, risk, diagnosis, fleet, memory, incident, missing,
                     baseline_visibility=None):
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
        baseline_visibility = baseline_visibility or {}
        if baseline_visibility.get("status") in {"INSUFFICIENT", "ELIGIBILITY_UNKNOWN"}:
            limitations.append(
                "Historical baseline " + baseline_visibility["status"].lower()
                + ": " + (baseline_visibility.get("reason") or "baseline evidence unavailable")
            )
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
