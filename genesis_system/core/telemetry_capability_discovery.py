"""Read-only inventory of observed telemetry and supported Genesis analyses."""

import math
from numbers import Real

from feature_contract import RAW_FEATURES
from ros2_telemetry_adapter import DEFAULT_KEY_MAPPINGS
from telemetry_pattern_engine import PATTERN_THRESHOLDS


# This catalog is the telemetry vocabulary supported by Genesis inputs. It is
# based on the shared feature contract, plus the existing state/time/derived
# values consumed by the streaming and analysis paths.
_TELEMETRY_FIELDS = tuple(dict.fromkeys((
    *(field for field in RAW_FEATURES if field not in {"manufacturer", "robot_type"}),
    "thermal_rise", "robot_state", "time_step",
)))
_NUMERIC_FIELDS = frozenset(_TELEMETRY_FIELDS) - {"robot_state"}
_BATTERY_SIGNAL_FIELDS = frozenset({
    "battery_level", "battery_voltage", "battery_current", "voltage_drop",
})
_PATTERN_SOURCE_FIELDS = (
    "motor_temperature", "thermal_rise", "battery_level", "battery_voltage",
)
_MIN_PATTERN_OBSERVATIONS = int(PATTERN_THRESHOLDS["minimum_observations"])
_MIN_THERMAL_WORKLOAD_PAIRS = int(PATTERN_THRESHOLDS["thermal_workload_coobservations"])
_ALIASES = {
    source: target for source, target in DEFAULT_KEY_MAPPINGS.items()
}
_ALIASES.update({
    "motor_temp": "motor_temperature",
    "motorTemperature": "motor_temperature",
    "ambient_temp": "ambient_temperature",
    "ambientTemperature": "ambient_temperature",
    "battery": "battery_level",
    "batteryPercentage": "battery_level",
    "batteryVoltage": "battery_voltage",
    "batteryCurrent": "battery_current",
    "batteryTemperature": "battery_temperature",
    "powerConsumption": "power_consumption",
    "voltageDrop": "voltage_drop",
    "temperatureUnit": "_unit_metadata",
    "ambientTemperatureUnit": "_unit_metadata",
    "temp_unit": "_unit_metadata",
    "ambient_temp_unit": "_unit_metadata",
    "state": "robot_state",
    "status": "robot_state",
    "robotType": "robot_type",
    "brand": "manufacturer",
    "id": "robot_id",
})
_ENVELOPE_FIELDS = frozenset({"identity", "telemetry", "source", "source_metadata", "limitations"})
_SIMULATOR_FIELDS = frozenset({
    "failure_event", "failure_type", "recovery_event", "label",
    "failure_type_label", "battery_health", "battery_stress",
    "degradation_level", "health", "initial_health",
})


def _flatten(record):
    if not isinstance(record, dict):
        raise ValueError("observations must contain telemetry objects")
    if "telemetry" not in record:
        return dict(record)
    telemetry = record.get("telemetry")
    identity = record.get("identity") or {}
    if not isinstance(telemetry, dict) or not isinstance(identity, dict):
        raise ValueError("observation identity and telemetry must be objects")
    return {
        **identity,
        **telemetry,
        "source_metadata": record.get("source_metadata") or {},
        "limitations": record.get("limitations") or [],
    }


def _canonical(record):
    result = {}
    for key, value in record.items():
        canonical = _ALIASES.get(key, key)
        if canonical not in result or result[canonical] is None:
            result[canonical] = value
    return result


def _valid(field, value):
    if value is None:
        return False
    if field in _NUMERIC_FIELDS:
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
            return False
        if field == "battery_level" and not 0.0 <= float(value) <= 100.0:
            return False
        return True
    if field == "robot_state":
        return isinstance(value, str) and bool(value.strip())
    return True


def discover_capabilities(
    observations,
    robot_identity=None,
    *,
    observation_quality=None,
    risk_model_available=False,
    diagnosis_model_available=False,
):
    """Describe observed telemetry, quality, and analysis sufficiency.

    ``observations`` must be chronological and belong to one robot. This
    function inventories evidence only; it never changes any Genesis decision.
    """
    if not isinstance(observations, (list, tuple)):
        raise ValueError("observations must be a chronological list of telemetry records")
    rows = [_canonical(_flatten(row)) for row in observations]
    identity = dict(robot_identity or {})
    known = set(_TELEMETRY_FIELDS) | set(RAW_FEATURES) | set(_ALIASES) | {
        "robot_id", "manufacturer", "robot_type", "time_step", "thermal_rise",
        "_unit_metadata",
    }
    unknown_fields = sorted({
        key for row in rows for key in row
        if key not in known and key not in _ENVELOPE_FIELDS and key not in _SIMULATOR_FIELDS
    })

    coverage = {}
    invalid_measurements = []
    missing_observation_fields = []
    for field in _TELEMETRY_FIELDS:
        observed = 0
        missing_count = 0
        invalid_count = 0
        for index, row in enumerate(rows):
            value = row.get(field)
            if value is None:
                missing_count += 1
            elif not _valid(field, value):
                invalid_count += 1
                invalid_measurements.append({"observation_index": index, "field": field})
            else:
                observed += 1
        coverage[field] = {
            "observed_count": observed,
            "missing_count": missing_count,
            "invalid_count": invalid_count,
            "latest_available": bool(rows and _valid(field, rows[-1].get(field))),
        }
        if observed == 0:
            missing_observation_fields.append(field)

    available = [field for field in _TELEMETRY_FIELDS if coverage[field]["observed_count"]]
    missing = [field for field in _TELEMETRY_FIELDS if field not in available]
    measurement_count = sum(coverage[field]["observed_count"] for field in _TELEMETRY_FIELDS)
    if not rows:
        quality_status = "UNAVAILABLE"
    elif not measurement_count:
        quality_status = "INSUFFICIENT"
    elif invalid_measurements or missing_observation_fields or unknown_fields:
        quality_status = "DEGRADED"
    else:
        quality_status = "AVAILABLE"

    def has(field):
        return coverage[field]["observed_count"] > 0

    def latest_has(field):
        return coverage[field]["latest_available"]

    def capability(name, required, *, status, reason=None, available_data=None, missing_data=None):
        return {
            "capability": name,
            "status": status,
            "required_data": list(required),
            "available_data": list(available_data or []),
            "missing_data": list(missing_data or []),
            "reason": reason,
        }

    thermal_fields = ("motor_temperature",)
    thermal_status = (
        "UNAVAILABLE" if not has("motor_temperature") else
        "AVAILABLE" if latest_has("motor_temperature") else "DEGRADED"
    )
    capabilities = [capability(
        "THERMAL_ANALYSIS", thermal_fields, status=thermal_status,
        reason=("motor_temperature was not observed" if thermal_status == "UNAVAILABLE" else
                "motor_temperature is missing or invalid in the latest observation" if thermal_status == "DEGRADED" else None),
        available_data=[field for field in thermal_fields if has(field)],
        missing_data=[field for field in thermal_fields if not latest_has(field)],
    )]

    rise_status = (
        "UNAVAILABLE" if not has("thermal_rise") else
        "AVAILABLE" if latest_has("thermal_rise") else "DEGRADED"
    )
    capabilities.append(capability(
        "THERMAL_RISE_ANALYSIS", ("thermal_rise",), status=rise_status,
        reason=("thermal_rise is unavailable from the observed fields" if rise_status == "UNAVAILABLE" else
                "thermal_rise is missing or invalid in the latest observation" if rise_status == "DEGRADED" else None),
        available_data=["thermal_rise"] if has("thermal_rise") else [],
        missing_data=[] if latest_has("thermal_rise") else ["thermal_rise"],
    ))

    battery_required = ("battery_voltage", "battery_current")
    battery_available = [field for field in battery_required if latest_has(field)]
    battery_any = any(has(field) for field in _BATTERY_SIGNAL_FIELDS)
    battery_status = (
        "AVAILABLE" if len(battery_available) == len(battery_required) else
        "DEGRADED" if battery_any else "UNAVAILABLE"
    )
    capabilities.append(capability(
        "BATTERY_ANALYSIS", battery_required, status=battery_status,
        reason=("no supported battery signal telemetry was observed" if battery_status == "UNAVAILABLE" else
                "only a subset of the voltage/current battery analysis inputs is available" if battery_status == "DEGRADED" else None),
        available_data=sorted(set(battery_available) | {field for field in _BATTERY_SIGNAL_FIELDS if latest_has(field)}),
        missing_data=[field for field in battery_required if not latest_has(field)],
    ))

    battery_temp_status = (
        "UNAVAILABLE" if not has("battery_temperature") else
        "AVAILABLE" if latest_has("battery_temperature") else "DEGRADED"
    )
    capabilities.append(capability(
        "BATTERY_TEMPERATURE_ANALYSIS", ("battery_temperature",), status=battery_temp_status,
        reason=("battery_temperature was not observed" if battery_temp_status == "UNAVAILABLE" else
                "battery_temperature is missing or invalid in the latest observation" if battery_temp_status == "DEGRADED" else None),
        available_data=["battery_temperature"] if has("battery_temperature") else [],
        missing_data=[] if latest_has("battery_temperature") else ["battery_temperature"],
    ))

    pattern_window = rows[-int(PATTERN_THRESHOLDS["window_size"]):]
    pattern_counts = {
        field: sum(_valid(field, row.get(field)) for row in pattern_window)
        for field in _PATTERN_SOURCE_FIELDS
    }
    max_pattern_history = max(pattern_counts.values(), default=0)
    pattern_status = (
        "UNAVAILABLE" if max_pattern_history == 0 else
        "AVAILABLE" if len(pattern_window) >= _MIN_PATTERN_OBSERVATIONS and max_pattern_history >= _MIN_PATTERN_OBSERVATIONS else
        "INSUFFICIENT"
    )
    pattern_inputs = [field for field, count in pattern_counts.items() if count >= _MIN_PATTERN_OBSERVATIONS]
    capabilities.append(capability(
        "TEMPORAL_PATTERN_ANALYSIS", _PATTERN_SOURCE_FIELDS, status=pattern_status,
        reason=("no thermal or battery series supported by TelemetryPatternEngine was observed" if pattern_status == "UNAVAILABLE" else
                f"requires at least {_MIN_PATTERN_OBSERVATIONS} observations with a supported thermal or battery measurement" if pattern_status == "INSUFFICIENT" else None),
        available_data=pattern_inputs,
        missing_data=[field for field in _PATTERN_SOURCE_FIELDS if field not in pattern_inputs],
    ))

    thermal_workload_pairs = sum(
        _valid("motor_temperature", row.get("motor_temperature"))
        and _valid("workload", row.get("workload"))
        for row in pattern_window
    )
    cooccurrence_status = (
        "AVAILABLE" if thermal_workload_pairs >= _MIN_THERMAL_WORKLOAD_PAIRS else
        "INSUFFICIENT" if thermal_workload_pairs or has("motor_temperature") or has("workload") else
        "UNAVAILABLE"
    )
    capabilities.append(capability(
        "THERMAL_WORKLOAD_PATTERN", ("motor_temperature", "workload"),
        status=cooccurrence_status,
        reason=(None if cooccurrence_status == "AVAILABLE" else
                f"requires {_MIN_THERMAL_WORKLOAD_PAIRS} paired thermal/workload observations" if cooccurrence_status == "INSUFFICIENT" else
                "thermal and workload telemetry were not observed"),
        available_data=[field for field in ("motor_temperature", "workload") if has(field)],
        missing_data=[field for field in ("motor_temperature", "workload") if not latest_has(field)],
    ))

    engineering_fields = ("motor_temperature", "thermal_rise", "battery_level", "voltage_drop", "battery_current")
    engineering_available = [field for field in engineering_fields if latest_has(field)]
    engineering_status = "AVAILABLE" if engineering_available else "UNAVAILABLE"
    capabilities.append(capability(
        "ENGINEERING_SIGNAL_ANALYSIS", engineering_fields,
        status=engineering_status,
        reason=None if engineering_available else "no telemetry used by ReliabilitySignal is available",
        available_data=engineering_available,
        missing_data=[field for field in engineering_fields if not latest_has(field)],
    ))

    if risk_model_available:
        capabilities.append(capability(
            "ML_RISK_INFERENCE", (), status="AVAILABLE",
            reason=None,
        ))
    else:
        capabilities.append(capability(
            "ML_RISK_INFERENCE", (), status="UNAVAILABLE",
            reason="No fitted risk model is configured in the current Genesis facade.",
        ))
    if diagnosis_model_available:
        capabilities.append(capability(
            "FAILURE_TYPE_DIAGNOSIS", (), status="AVAILABLE",
            reason=None,
        ))
    else:
        capabilities.append(capability(
            "FAILURE_TYPE_DIAGNOSIS", (), status="UNAVAILABLE",
            reason="No diagnosis model is configured in the current Genesis facade.",
        ))

    unavailable = [item for item in capabilities if item["status"] != "AVAILABLE"]
    limitations = []
    if not rows:
        limitations.append("No observations were supplied to capability discovery.")
    if missing_observation_fields:
        limitations.append("Some supported telemetry fields were not observed in this session.")
    if invalid_measurements:
        limitations.append("One or more telemetry values were invalid or unusable.")
    if unknown_fields:
        limitations.append("Unrecognized telemetry fields were supplied and are not interpreted by this Genesis contract.")
    source_limitations = list(dict.fromkeys(
        limitation
        for row in rows
        for limitation in (row.get("limitations") or [])
        if isinstance(limitation, str) and limitation
    ))
    limitations.extend(source_limitations)
    for item in unavailable:
        if item["reason"]:
            limitations.append(f"{item['capability']}: {item['reason']}")

    quality = {
        "status": quality_status,
        "observation_count": len(rows),
        "field_coverage": coverage,
        "invalid_measurements": invalid_measurements,
        "unrecognized_fields": unknown_fields,
        "source_limitations": source_limitations,
        "observation_quality_summary": {
            "status": (observation_quality or {}).get("status", "UNAVAILABLE"),
            "groups": {
                name: group.get("status", "UNAVAILABLE")
                for name, group in ((observation_quality or {}).get("groups") or {}).items()
            },
        },
    }
    return {
        "robot_identity": {
            key: identity.get(key)
            for key in ("robot_id", "manufacturer", "robot_type")
            if identity.get(key) is not None
        },
        "observation_count": len(rows),
        "available_telemetry": available,
        "missing_telemetry": missing,
        "data_quality": quality,
        "analysis_capabilities": capabilities,
        "unavailable_capabilities": unavailable,
        "limitations": list(dict.fromkeys(limitations)),
    }

