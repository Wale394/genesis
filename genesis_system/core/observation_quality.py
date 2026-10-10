"""Conservative, deterministic checks on telemetry evidence quality.

This layer describes observation availability and consistency. It does not
estimate failure probability or alter model features or thresholds.
"""

import math
from numbers import Real

from feature_contract import (
    DEPLOYABLE_FEATURES,
    HISTORY_COUNT_FIELD,
    ROUND_DIGITS,
    minimum_history_for,
)


AVAILABLE = "AVAILABLE"
DEGRADED = "DEGRADED"
INSUFFICIENT = "INSUFFICIENT"


GROUPS = {
    "thermal": {
        "fields": (
            "motor_temperature", "ambient_temperature", "thermal_rise",
            "temperature_change", "temperature_rate_3", "temperature_rate_5",
            "temperature_avg_3", "temperature_avg_5", "thermal_rise_rate_3",
            "thermal_rise_max_3", "thermal_rise_max_5", "thermal_rise_avg_3",
            "thermal_rise_avg_5", "thermal_elevated_persistence",
            "temperature_acceleration",
        ),
        "core": ("motor_temperature", "ambient_temperature"),
        "temporal": (
            "temperature_change", "temperature_rate_3", "temperature_rate_5",
            "temperature_avg_3", "temperature_avg_5", "thermal_rise_rate_3",
            "thermal_rise_max_3", "thermal_rise_max_5", "thermal_rise_avg_3",
            "thermal_rise_avg_5", "thermal_elevated_persistence",
            "temperature_acceleration",
        ),
    },
    "battery": {
        "fields": (
            "battery_level", "battery_voltage", "battery_current",
            "battery_temperature", "voltage_drop", "battery_change",
            "battery_drop_rate_3", "battery_voltage_change",
            "battery_voltage_drop_rate_3", "battery_current_change",
            "battery_temperature_change", "battery_temperature_rate_3",
            "battery_decline_3", "battery_decline_5",
            "low_battery_persistence", "battery_voltage_decline_3",
            "battery_current_change_3",
        ),
        "core": ("battery_level", "battery_voltage"),
        "temporal": (
            "battery_change", "battery_drop_rate_3", "battery_voltage_change",
            "battery_voltage_drop_rate_3", "battery_current_change",
            "battery_temperature_change", "battery_temperature_rate_3",
            "battery_decline_3", "battery_decline_5", "low_battery_persistence",
            "battery_voltage_decline_3", "battery_current_change_3",
        ),
    },
    "workload": {
        "fields": ("workload", "power_consumption", "battery_current", "power_change", "power_rate_3"),
        "core": ("workload", "power_consumption"),
        "temporal": ("power_change", "power_rate_3"),
    },
}

_NUMERIC_FIELDS = frozenset(
    field
    for group in GROUPS.values()
    for field in group["fields"]
)
_RAW_HISTORY_FIELDS = (
    "motor_temperature", "ambient_temperature", "battery_level",
    "battery_voltage", "battery_current", "battery_temperature",
    "power_consumption", "workload",
)


class ObservationQuality:
    """Assess missingness, warm-up, validity, and consistency by signal group."""

    def assess(self, feature_record, historical_records=None):
        historical_records = list(historical_records or [])
        groups = {}
        for name, definition in GROUPS.items():
            groups[name] = self._assess_group(
                name, definition, feature_record, historical_records
            )

        statuses = [item["status"] for item in groups.values()]
        overall = AVAILABLE if all(s == AVAILABLE for s in statuses) else (
            INSUFFICIENT if all(s == INSUFFICIENT for s in statuses) else DEGRADED
        )
        missing_model_features = [
            name for name in DEPLOYABLE_FEATURES
            if feature_record.get(name) is None
        ]
        history_count = self._history_count(feature_record, historical_records)
        required_history = minimum_history_for(DEPLOYABLE_FEATURES)
        prediction_ready = (
            not missing_model_features and history_count >= required_history
        )
        field_groups = self._field_groups(groups)
        return {
            "status": overall,
            "groups": groups,
            "field_groups": field_groups,
            "prediction_ready": prediction_ready,
            "history": {
                "available_prior_observations": history_count,
                "required_prior_observations": required_history,
            },
            "missing_model_features": missing_model_features,
            "any_major_group_limited": any(
                item["status"] != AVAILABLE for item in groups.values()
            ),
        }

    @staticmethod
    def _field_groups(groups):
        mapping = {}
        for group_name, definition in GROUPS.items():
            for field in definition["fields"]:
                mapping.setdefault(field, []).append(group_name)

        result = {}
        for field, group_names in mapping.items():
            statuses = [groups[name]["status"] for name in group_names]
            if INSUFFICIENT in statuses:
                status = INSUFFICIENT
            elif DEGRADED in statuses:
                status = DEGRADED
            else:
                status = AVAILABLE
            result[field] = {
                "groups": list(group_names),
                "status": status,
            }
        return result

    @staticmethod
    def _history_count(feature_record, historical_records):
        count = feature_record.get(HISTORY_COUNT_FIELD)
        if isinstance(count, int) and count >= 0:
            return count
        return len(historical_records)

    def _assess_group(self, name, definition, record, history):
        issues = []
        fields = definition["fields"]
        core = definition["core"]
        temporal = definition["temporal"]
        missing = [field for field in fields if record.get(field) is None]
        missing_core = [field for field in core if record.get(field) is None]
        if missing:
            issues.append({"check": "missing_values", "fields": missing})

        history_count = self._history_count(record, history)
        required_history = minimum_history_for(temporal)
        history_ready = history_count >= required_history
        if not history_ready:
            issues.append({
                "check": "insufficient_history",
                "available": history_count,
                "required": required_history,
            })

        invalid = []
        for field in fields:
            value = record.get(field)
            if value is None:
                continue
            if field in _NUMERIC_FIELDS and (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(float(value))
            ):
                invalid.append(field)
                continue
            # Only enforce bounds that follow directly from the field's
            # representation, rather than general physical assumptions.
            if field == "battery_level" and not 0.0 <= float(value) <= 100.0:
                invalid.append(field)
        if invalid:
            issues.append({"check": "invalid_values", "fields": invalid})

        jumps = self._implausible_jumps(record, history, fields)
        if jumps:
            issues.append({"check": "abrupt_change", "fields": jumps})

        static_fields = self._static_when_variation_expected(name, record, history)
        if static_fields:
            issues.append({"check": "unexpected_static_sensor", "fields": static_fields})

        disagreements = self._related_measurement_disagreements(record)
        if name == "thermal" and disagreements:
            issues.append({
                "check": "related_measurement_disagreement",
                "fields": disagreements,
            })

        if missing_core or not history_ready:
            status = INSUFFICIENT
        elif issues:
            status = DEGRADED
        else:
            status = AVAILABLE
        return {
            "status": status,
            "missing_fields": missing,
            "issues": issues,
        }

    @staticmethod
    def _related_measurement_disagreements(record):
        motor = record.get("motor_temperature")
        ambient = record.get("ambient_temperature")
        rise = record.get("thermal_rise")
        numeric = (motor, ambient, rise)
        if not all(isinstance(v, Real) and not isinstance(v, bool) and math.isfinite(float(v)) for v in numeric):
            return []
        expected = round(float(motor) - float(ambient), ROUND_DIGITS)
        tolerance = 10 ** (-ROUND_DIGITS)
        return ["thermal_rise"] if abs(float(rise) - expected) > tolerance else []

    @staticmethod
    def _static_when_variation_expected(name, record, history):
        window = history[-4:] + [record]
        if len(window) < 5:
            return []

        def static(field):
            values = [item.get(field) for item in window]
            return all(isinstance(v, Real) and not isinstance(v, bool) for v in values) and len(set(values)) == 1

        def varies(field):
            values = [item.get(field) for item in window]
            valid = [v for v in values if isinstance(v, Real) and not isinstance(v, bool)]
            return len(valid) >= 2 and len(set(valid)) > 1

        if name == "thermal" and static("motor_temperature") and (
            varies("workload") or varies("power_consumption")
        ):
            return ["motor_temperature"]
        if name == "battery" and static("battery_level") and static("battery_voltage") and (
            varies("battery_current") or varies("power_consumption")
        ):
            return ["battery_level", "battery_voltage"]
        if name == "workload" and static("workload") and varies("motor_temperature"):
            return ["workload"]
        return []

    @staticmethod
    def _implausible_jumps(record, history, fields):
        flagged = []
        # A conservative, per-sensor robust outlier rule. It needs at least
        # five previous readings and adapts to that robot's observed changes.
        for field in fields:
            current = record.get(field)
            values = [item.get(field) for item in history]
            if not isinstance(current, Real) or isinstance(current, bool):
                continue
            if len(values) < 5 or any(not isinstance(v, Real) or isinstance(v, bool) for v in values[-5:]):
                continue
            prior = [float(v) for v in values[-5:]]
            changes = [prior[i] - prior[i - 1] for i in range(1, len(prior))]
            center = sorted(changes)[len(changes) // 2]
            deviations = sorted(abs(change - center) for change in changes)
            mad = deviations[len(deviations) // 2]
            typical = sorted(abs(change) for change in changes)[len(changes) // 2]
            limit = max(8.0 * mad, 8.0 * typical, 10 ** (-ROUND_DIGITS))
            if abs(float(current) - prior[-1] - center) > limit:
                flagged.append(field)
        return flagged
