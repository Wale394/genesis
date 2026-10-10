"""Public Genesis facade over the existing local reliability pipeline."""

import json
import math
from numbers import Real
from collections.abc import Mapping

from baseline_engine import BaselineEngine
from comparison_engine import ComparisonEngine
from decision_pipeline import DecisionPipeline
from evidence_engine import EvidenceEngine
from fleet_baseline import FleetBaseline
from history import History
from incident_manager import IncidentManager
from normalizer import Normalizer
from recommendation_engine import RecommendationEngine
from reliability_memory import ReliabilityMemory
from reliability_state import ReliabilityState
from telemetry_features import TelemetryFeatureBuilder
from telemetry_capability_discovery import discover_capabilities
from telemetry_sampling_context import analyze_sampling_intervals, validate_sampling_context


_TELEMETRY_FIELDS = (
    "motor_temperature", "ambient_temperature", "battery_level",
    "battery_voltage", "battery_current", "battery_temperature",
    "power_consumption", "voltage_drop", "workload", "robot_state",
)
_NUMERIC_FIELDS = frozenset(_TELEMETRY_FIELDS) - {"robot_state"}


class Genesis:
    """Small product-facing facade; inference and lifecycle remain pipeline-owned."""

    def __init__(self, *, peer_records=None, historical_incidents=None):
        self._feature_builder = TelemetryFeatureBuilder()
        self._normalizer = Normalizer()
        self._history = History()
        self._incident_manager = IncidentManager(self._history)
        self._memory = ReliabilityMemory()
        for incident in historical_incidents or []:
            if not isinstance(incident, Mapping):
                raise ValueError("historical_incidents must contain incident report objects")
            try:
                self._memory.store_incident(dict(incident))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Malformed historical incident: {exc}") from exc
        self._peer_records = list(peer_records or [])
        self._pipeline = DecisionPipeline(
            prediction_engine=None,
            diagnosis_engine=None,
            recommendation_engine=RecommendationEngine(),
            reliability_state=ReliabilityState(),
            incident_manager=self._incident_manager,
            evidence_engine=EvidenceEngine(),
            comparison_engine=ComparisonEngine(history_window=10),
            baseline_engine=BaselineEngine(minimum_records=10),
            reliability_memory=self._memory,
            fleet_baseline=FleetBaseline(),
        )
        self._records_by_robot = {}
        self._capability_records_by_robot = {}
        # Keep the existing time_step values plus None where Genesis had to
        # assign an ingestion-order fallback; sampling analysis must use only
        # source-supplied timestamps, never treat fallback indices as seconds.
        self._sampling_time_steps_by_robot = {}
        self._states_by_robot = {}
        self._last_time_by_robot = {}

    def investigate(self, telemetry_records, *, peer_records=None, sampling_context=None):
        """Process one observation or a chronological list and return the latest report.

        Inputs may be normalized flat telemetry, ``identity``/``telemetry``
        snapshots, or records accepted by the existing ``Normalizer``.
        """
        if isinstance(telemetry_records, Mapping):
            input_records = [telemetry_records]
        elif isinstance(telemetry_records, (list, tuple)):
            input_records = list(telemetry_records)
        else:
            raise ValueError("telemetry_records must be a telemetry object or a non-empty list of objects")
        if not input_records:
            raise ValueError("telemetry_records must contain at least one observation")

        sampling_context = validate_sampling_context(sampling_context)

        current_peers = self._peer_records if peer_records is None else self._validate_peers(peer_records)
        latest_result = None
        processed = []
        timeline_events_by_robot = {}
        latest_identity = None
        for index, item in enumerate(input_records, start=1):
            try:
                source_record = self._flatten(item)
                if isinstance(item, Mapping) and "telemetry" in item:
                    source_record["source_metadata"] = item.get("source_metadata") or {}
                    source_record["limitations"] = item.get("limitations") or []
                identity, telemetry = self._normalize_record(item)
                latest_identity = identity
                robot_id = identity["robot_id"]
                previous_time = self._last_time_by_robot.get(robot_id)
                time_step = telemetry.get("time_step")
                source_time_step = time_step
                if time_step is None:
                    time_step = 1 if previous_time is None else previous_time + 1
                if (
                    isinstance(time_step, bool)
                    or not isinstance(time_step, Real)
                    or not math.isfinite(float(time_step))
                ):
                    raise ValueError("time_step must be a finite number")
                if previous_time is not None and time_step <= previous_time:
                    raise ValueError(
                        f"time_step {time_step} is not later than the previous observation {previous_time} for {robot_id}"
                    )
                telemetry["time_step"] = time_step
                self._validate_values(telemetry)
                snapshot = {"identity": identity, "telemetry": telemetry}
                feature_record = self._feature_builder.build(snapshot)
                historical = self._records_by_robot.setdefault(robot_id, [])
                previous_steps = self._sampling_time_steps_by_robot.get(robot_id, [])
                sampling_analysis = analyze_sampling_intervals(
                    previous_steps + [time_step], sampling_context
                )
                step_peers = [
                    peer for peer in current_peers
                    if peer.get("time_step") is None or peer.get("time_step") == time_step
                ]
                latest_result = self._pipeline.evaluate(
                    feature_record,
                    previous_state=self._states_by_robot.get(robot_id),
                    historical_records=historical,
                    fleet_records=step_peers,
                    sampling_analysis=sampling_analysis,
                )
                timeline_events_by_robot.setdefault(robot_id, []).extend(
                    latest_result.get("timeline", {}).get("events", [])
                )
                historical.append(feature_record)
                capability_record = dict(source_record)
                capability_record.update(identity)
                capability_record.update(telemetry)
                capability_record["thermal_rise"] = feature_record.get("thermal_rise")
                self._capability_records_by_robot.setdefault(robot_id, []).append(capability_record)
                self._sampling_time_steps_by_robot.setdefault(robot_id, []).append(source_time_step)
                self._states_by_robot[robot_id] = latest_result["state"]
                self._last_time_by_robot[robot_id] = time_step
                processed.append((
                    robot_id,
                    time_step,
                    latest_result["state"],
                    feature_record.get("motor_temperature"),
                ))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Malformed telemetry observation {index}: {exc}") from exc

        public_result = self._public_result(latest_result, processed)
        robot_id = latest_identity["robot_id"]
        timeline_events = sorted(
            timeline_events_by_robot.get(robot_id, []),
            key=lambda event: event.get("time_step", 0),
        )
        public_result["evidence_timeline"] = {
            "event_count": len(timeline_events), "events": timeline_events,
        }
        public_result["capability_discovery"] = discover_capabilities(
            self._capability_records_by_robot.get(robot_id, []),
            robot_identity=latest_identity,
            observation_quality=latest_result.get("observation_quality"),
            risk_model_available=self._pipeline.prediction_engine is not None,
            diagnosis_model_available=self._pipeline.diagnosis_engine is not None,
        )
        return public_result

    @staticmethod
    def _flatten(record):
        if not isinstance(record, Mapping):
            raise ValueError("each telemetry observation must be an object")
        source = dict(record)
        if "telemetry" in source:
            telemetry = source.get("telemetry")
            identity = source.get("identity", {})
            if not isinstance(telemetry, Mapping) or not isinstance(identity, Mapping):
                raise ValueError("identity and telemetry must be objects")
            return {**dict(identity), **dict(telemetry)}
        return source

    def _normalize_record(self, record):
        source = self._flatten(record)
        identity = {
            "robot_id": source.get("robot_id", source.get("id")),
            "manufacturer": source.get("manufacturer", source.get("brand")),
            "robot_type": source.get("robot_type", source.get("robotType")),
        }
        if identity["robot_id"] in (None, ""):
            raise ValueError("robot_id (or id) is required")

        raw_input = any(key in source for key in (
            "motorTemperature", "motor_temp", "temperatureUnit", "temperature_unit", "temp_unit",
        ))
        if raw_input:
            try:
                normalized = self._normalizer.normalize(source)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"normalization failed: {exc}") from exc
            identity = {
                "robot_id": normalized["robot_id"],
                "manufacturer": normalized.get("manufacturer"),
                "robot_type": normalized.get("robot_type"),
            }
            telemetry = {field: normalized.get(field) for field in _TELEMETRY_FIELDS}
        else:
            telemetry = {field: source.get(field) for field in _TELEMETRY_FIELDS}
            # Accept normalized aliases without invoking raw-unit conversion.
            if telemetry["motor_temperature"] is None:
                telemetry["motor_temperature"] = source.get("motor_temp")
            if telemetry["ambient_temperature"] is None:
                telemetry["ambient_temperature"] = source.get("ambient_temp")
            if telemetry["battery_level"] is None:
                telemetry["battery_level"] = source.get("battery")
            if telemetry["robot_state"] is None:
                telemetry["robot_state"] = source.get("state", source.get("status"))
            state = telemetry.get("robot_state")
            if state in self._normalizer.state_mappings:
                telemetry["robot_state"] = self._normalizer.normalize_state(state)
            elif state not in (None, "working", "idle"):
                raise ValueError(f"unrecognized robot_state: {state!r}")

        telemetry["time_step"] = source.get("time_step")
        return identity, telemetry

    @staticmethod
    def _validate_values(telemetry):
        for field in _NUMERIC_FIELDS:
            value = telemetry.get(field)
            if value is None:
                continue
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(float(value))
            ):
                raise ValueError(f"{field} must be a finite number or null")

    @staticmethod
    def _validate_peers(peer_records):
        if not isinstance(peer_records, (list, tuple)):
            raise ValueError("peer_records must be a list of telemetry objects")
        if any(not isinstance(record, Mapping) for record in peer_records):
            raise ValueError("peer_records must contain telemetry objects")
        return [dict(record) for record in peer_records]

    @staticmethod
    def _public_result(result, processed):
        explanation = result["explanation"]
        identity = explanation.get("identity", {})
        public = {
            "robot": {
                "robot_id": result.get("robot_id"),
                "manufacturer": identity.get("manufacturer"),
                "robot_type": identity.get("robot_type"),
            },
            "reliability_state": {
                "current": result.get("state"),
                "previous": result.get("previous_state"),
                "transition": result.get("state_transition"),
            },
            "incident": result.get("incident"),
            "observation_quality": result.get("observation_quality"),
            "observations": explanation.get("observations", []),
            "temporal_evidence": explanation.get("temporal_evidence", []),
            "engineering_signals": result.get("risk", {}).get("engineering", {}),
            "ml_inference": explanation.get("ml_inference", {}),
            "fleet_context": result.get("fleet_context", {}),
            "historical_memory": explanation.get("historical_memory", {}),
            "evidence_synthesis": explanation.get("evidence_synthesis", {}),
            "evidence_timeline": result.get("timeline", {"event_count": 0, "events": []}),
            "sampling_analysis": result.get("sampling_analysis", {}),
            "recommendation": result.get("recommendation"),
            "human_action": explanation.get("human_action", {}),
            "outcome": explanation.get("outcome", {}),
            "limitations": explanation.get("limitations", []),
            "processing": {
                "observation_count": len(processed),
                "states": [
                    {"robot_id": robot_id, "time_step": step, "state": state}
                    for robot_id, step, state, _temperature in processed
                ],
                "telemetry": [
                    {"robot_id": robot_id, "time_step": step, "motor_temperature": temperature}
                    for robot_id, step, _state, temperature in processed
                ],
            },
        }
        try:
            return json.loads(json.dumps(public, ensure_ascii=False, allow_nan=False))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Genesis result is not JSON-compatible: {exc}") from exc
