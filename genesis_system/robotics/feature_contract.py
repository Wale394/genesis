"""Canonical deployable telemetry feature definitions.

All temporal windows include the current observation. History passed to
``build_features`` contains earlier observations for one robot, in time order.
Values that need more observations than are available are ``None``; callers
can use ``MINIMUM_HISTORY`` to enforce the warm-up period.
"""

from collections.abc import Mapping


RAW_FEATURES = (
    "manufacturer",
    "robot_type",
    "motor_temperature",
    "ambient_temperature",
    "battery_level",
    "battery_voltage",
    "battery_current",
    "battery_temperature",
    "power_consumption",
    "voltage_drop",
    "workload",
)

# This ordered list is the only feature schema used by the failure-risk model.
DEPLOYABLE_FEATURES = (
    "manufacturer",
    "robot_type",
    "motor_temperature",
    "ambient_temperature",
    "thermal_rise",
    "temperature_change",
    "temperature_rate_3",
    "temperature_rate_5",
    "temperature_avg_3",
    "temperature_avg_5",
    "thermal_rise_rate_3",
    "battery_level",
    "battery_voltage",
    "battery_current",
    "battery_temperature",
    "power_consumption",
    "voltage_drop",
    "battery_change",
    "battery_drop_rate_3",
    "battery_voltage_change",
    "battery_voltage_drop_rate_3",
    "battery_current_change",
    "battery_temperature_change",
    "battery_temperature_rate_3",
    "power_change",
    "power_rate_3",
    "workload",
    "thermal_rise_max_3",
    "thermal_rise_max_5",
    "thermal_rise_avg_3",
    "thermal_rise_avg_5",
    "thermal_elevated_persistence",
    "temperature_acceleration",
    "battery_decline_3",
    "battery_decline_5",
    "low_battery_persistence",
    "battery_voltage_decline_3",
    "battery_current_change_3",
)

# Diagnosis is based on the same observable telemetry and derived features as
# failure risk. This ordered allowlist is kept explicit so diagnosis training
# cannot acquire newly added risk inputs by implication.
DIAGNOSIS_FEATURES = (
    "manufacturer",
    "robot_type",
    "motor_temperature",
    "ambient_temperature",
    "thermal_rise",
    "temperature_change",
    "temperature_rate_3",
    "temperature_rate_5",
    "temperature_avg_3",
    "temperature_avg_5",
    "thermal_rise_rate_3",
    "battery_level",
    "battery_voltage",
    "battery_current",
    "battery_temperature",
    "power_consumption",
    "voltage_drop",
    "battery_change",
    "battery_drop_rate_3",
    "battery_voltage_change",
    "battery_voltage_drop_rate_3",
    "battery_current_change",
    "battery_temperature_change",
    "battery_temperature_rate_3",
    "power_change",
    "power_rate_3",
    "workload",
    "thermal_rise_max_3",
    "thermal_rise_max_5",
    "thermal_rise_avg_3",
    "thermal_rise_avg_5",
    "thermal_elevated_persistence",
    "temperature_acceleration",
    "battery_decline_3",
    "battery_decline_5",
    "low_battery_persistence",
    "battery_voltage_decline_3",
    "battery_current_change_3",
)

SIMULATOR_ONLY_FIELDS = frozenset({
    "battery_health",
    "battery_stress",
    "degradation_level",
    "health",
    "initial_health",
    "failure_event",
    "failure_type",
    "recovery_event",
    "label",
    "failure_type_label",
})

HISTORY_REQUIREMENTS = {
    "temperature_change": 1,
    "battery_change": 1,
    "battery_voltage_change": 1,
    "battery_current_change": 1,
    "battery_temperature_change": 1,
    "power_change": 1,
    "temperature_rate_3": 3,
    "thermal_rise_rate_3": 3,
    "battery_drop_rate_3": 3,
    "battery_voltage_drop_rate_3": 3,
    "battery_temperature_rate_3": 3,
    "power_rate_3": 3,
    "temperature_rate_5": 4,
    "temperature_avg_3": 2,
    "thermal_rise_max_3": 2,
    "thermal_rise_avg_3": 2,
    "battery_decline_3": 2,
    "battery_voltage_decline_3": 2,
    "battery_current_change_3": 2,
    "temperature_avg_5": 4,
    "thermal_rise_max_5": 4,
    "thermal_rise_avg_5": 4,
    "battery_decline_5": 4,
    "temperature_acceleration": 2,
}

MINIMUM_HISTORY = max(
    HISTORY_REQUIREMENTS.get(feature, 0)
    for feature in DEPLOYABLE_FEATURES
)
ROUND_DIGITS = 2
HISTORY_COUNT_FIELD = "_history_count"


def minimum_history_for(features=DEPLOYABLE_FEATURES):
    """Return the number of prior observations needed for these features."""
    return max(
        (HISTORY_REQUIREMENTS.get(feature, 0) for feature in features),
        default=0,
    )


def _rounded(value):
    if value is None:
        return None
    return round(float(value), ROUND_DIGITS)


def _enrich(record):
    enriched = dict(record)
    for field in RAW_FEATURES:
        if field in ("manufacturer", "robot_type"):
            value = enriched.get(field)
            enriched[field] = str(value) if value is not None else None
        else:
            enriched[field] = _rounded(enriched.get(field))
    motor = enriched.get("motor_temperature")
    ambient = enriched.get("ambient_temperature")
    enriched["thermal_rise"] = (
        _rounded(motor - ambient)
        if motor is not None and ambient is not None
        else None
    )
    return enriched


def _lagged_difference(current, history, field, steps, earlier_minus_current=False):
    if len(history) < steps:
        return None
    earlier = history[-steps].get(field)
    if current.get(field) is None or earlier is None:
        return None
    if earlier_minus_current:
        return earlier - current[field]
    return current[field] - earlier


def _window(current, history, field, size):
    records = (history[-(size - 1):] if size > 1 else []) + [current]
    values = [record.get(field) for record in records]
    if len(records) < size or any(value is None for value in values):
        return None
    return values


def _delta(current, previous, field):
    if not previous or current.get(field) is None or previous[-1].get(field) is None:
        return None
    return current[field] - previous[-1][field]


def _persistence(current, history, field, threshold, low=False):
    count = 0
    for record in reversed((history or []) + [current]):
        value = record.get(field)
        if value is None:
            break
        matches = value <= threshold if low else value >= threshold
        if not matches:
            break
        count += 1
    return count


def build_features(current, history=()):
    """Compute the authoritative deployable features for one observation.

    ``current`` and each history record use normalized telemetry field names.
    History must contain only prior observations from the same robot.
    """
    if not isinstance(current, Mapping):
        raise TypeError("current telemetry must be a mapping")
    history = [_enrich(record) for record in (history or ())]
    current = _enrich(current)
    result = {field: current.get(field) for field in RAW_FEATURES}
    result["thermal_rise"] = current["thermal_rise"]

    # Derived thermal rise is made available in the same history record used
    # by all subsequent rolling calculations.
    enriched = dict(current)

    for feature, field in (
        ("temperature_change", "motor_temperature"),
        ("battery_change", "battery_level"),
        ("battery_voltage_change", "battery_voltage"),
        ("battery_current_change", "battery_current"),
        ("battery_temperature_change", "battery_temperature"),
        ("power_change", "power_consumption"),
    ):
        result[feature] = _rounded(_delta(enriched, history, field))

    for feature, field, steps, positive_decline in (
        ("temperature_rate_3", "motor_temperature", 3, False),
        ("temperature_rate_5", "motor_temperature", 4, False),
        ("thermal_rise_rate_3", "thermal_rise", 3, False),
        ("battery_drop_rate_3", "battery_level", 3, True),
        ("battery_voltage_drop_rate_3", "battery_voltage", 3, True),
        ("battery_temperature_rate_3", "battery_temperature", 3, False),
        ("power_rate_3", "power_consumption", 3, False),
    ):
        result[feature] = _rounded(_lagged_difference(
            enriched, history, field, steps, positive_decline
        ))

    for feature, field, size in (
        ("temperature_avg_3", "motor_temperature", 3),
        ("temperature_avg_5", "motor_temperature", 5),
        ("thermal_rise_max_3", "thermal_rise", 3),
        ("thermal_rise_max_5", "thermal_rise", 5),
        ("thermal_rise_avg_3", "thermal_rise", 3),
        ("thermal_rise_avg_5", "thermal_rise", 5),
        ("battery_decline_3", "battery_level", 3),
        ("battery_decline_5", "battery_level", 5),
        ("battery_voltage_decline_3", "battery_voltage", 3),
        ("battery_current_change_3", "battery_current", 3),
    ):
        values = _window(enriched, history, field, size)
        if values is None:
            result[feature] = None
        elif feature.endswith("_avg_3") or feature.endswith("_avg_5"):
            result[feature] = _rounded(sum(values) / len(values))
        elif feature.startswith("thermal_rise_max_"):
            result[feature] = _rounded(max(values))
        elif feature.startswith("battery_decline_") or feature == "battery_voltage_decline_3":
            result[feature] = _rounded(values[0] - values[-1])
        else:
            result[feature] = _rounded(values[-1] - values[0])

    result["thermal_elevated_persistence"] = _persistence(
        enriched, history, "thermal_rise", 20
    )
    result["low_battery_persistence"] = _persistence(
        enriched, history, "battery_level", 35, low=True
    )

    if len(history) < 2:
        result["temperature_acceleration"] = None
    else:
        current_change = result["temperature_change"]
        previous_change = _delta(history[-1], history[:-1], "motor_temperature")
        result["temperature_acceleration"] = (
            _rounded(current_change - previous_change)
            if current_change is not None and previous_change is not None
            else None
        )

    return {feature: result.get(feature) for feature in DEPLOYABLE_FEATURES}
