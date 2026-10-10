"""ROS 2 diagnostic-message translation into Genesis telemetry snapshots.

This module deliberately has no ROS imports. It accepts ROS-like
DiagnosticArray/DiagnosticStatus/KeyValue objects by their public attributes,
and only translates observations; it never infers robot condition or sends
commands.
"""

from collections import defaultdict
from collections.abc import Mapping
import math
import re
from numbers import Real


# Exact diagnostic key names map to canonical Genesis fields. Vendor adapters
# can extend or override this mapping through ``key_mappings``.
DEFAULT_KEY_MAPPINGS = {
    "motor_temperature": "motor_temperature",
    "motor_temp": "motor_temperature",
    "ambient_temperature": "ambient_temperature",
    "ambient_temp": "ambient_temperature",
    "battery_level": "battery_level",
    "battery_percentage": "battery_level",
    "battery_voltage": "battery_voltage",
    "battery_current": "battery_current",
    "battery_temperature": "battery_temperature",
    "voltage_drop": "voltage_drop",
    "power_consumption": "power_consumption",
    "workload": "workload",
    "robot_state": "robot_state",
    "state": "robot_state",
    "status": "robot_state",
}

_NUMERIC_UNITS = {
    "motor_temperature": "temperature",
    "ambient_temperature": "temperature",
    "battery_temperature": "temperature",
    "battery_voltage": "voltage",
    "voltage_drop": "voltage",
    "battery_current": "current",
    "battery_level": "percentage",
    "workload": "percentage",
    "power_consumption": "power",
}

_UNIT_ALIASES = {
    "temperature": {
        "c": "C", "°c": "C", "degc": "C", "celsius": "C",
        "f": "F", "°f": "F", "degf": "F", "fahrenheit": "F",
        "k": "K", "kelvin": "K",
    },
    "voltage": {"v": "V", "volt": "V", "volts": "V"},
    "current": {"a": "A", "amp": "A", "amps": "A", "ampere": "A", "amperes": "A"},
    "percentage": {"%": "%", "percent": "%", "percentage": "%"},
    "power": {"w": "W", "watt": "W", "watts": "W"},
}

_NUMBER_WITH_UNIT = re.compile(
    r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([^\d\s].*?)?\s*$"
)
_STATE_ALIASES = {
    "working": "working", "active": "working", "running": "working",
    "operating": "working", "idle": "idle", "standby": "idle",
}


def _get(value, name, default=None):
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _json_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    sec = _get(value, "sec")
    nanosec = _get(value, "nanosec")
    if sec is not None and nanosec is not None:
        return {"sec": int(sec), "nanosec": int(nanosec)}
    return str(value)


class ROS2TelemetryAdapter:
    """Translate ROS 2 DiagnosticArray-like input to a Genesis snapshot.

    ``key_mappings`` maps exact source KeyValue names to Genesis field names.
    ``field_units`` is an explicit per-field unit declaration for sources that
    do not include units in the diagnostic array. Message-provided unit keys
    (for example ``battery_voltage_unit``) take precedence.
    """

    def __init__(
        self,
        robot_id,
        manufacturer=None,
        robot_type=None,
        *,
        key_mappings=None,
        field_units=None,
    ):
        if robot_id is None or not str(robot_id).strip():
            raise ValueError("robot_id is required for ROS 2 telemetry ingestion")

        self.identity = {"robot_id": str(robot_id)}
        if manufacturer is not None:
            self.identity["manufacturer"] = str(manufacturer)
        if robot_type is not None:
            self.identity["robot_type"] = str(robot_type)

        self.key_mappings = dict(DEFAULT_KEY_MAPPINGS)
        if key_mappings:
            self.key_mappings.update(dict(key_mappings))
        supported = set(_NUMERIC_UNITS) | {"robot_state"}
        invalid_targets = set(self.key_mappings.values()) - supported
        if invalid_targets:
            raise ValueError("Unsupported Genesis diagnostic targets: " + ", ".join(sorted(invalid_targets)))

        self.field_units = dict(field_units or {})
        invalid_unit_fields = set(self.field_units) - set(_NUMERIC_UNITS)
        if invalid_unit_fields:
            raise ValueError("Units are not defined for: " + ", ".join(sorted(invalid_unit_fields)))

    def adapt(self, diagnostic_array, *, time_step=None):
        """Return a Genesis ``identity``/``telemetry`` snapshot plus source metadata."""
        if diagnostic_array is None:
            raise ValueError("DiagnosticArray message is required")
        statuses = _get(diagnostic_array, "status")
        if statuses is None or not isinstance(statuses, (list, tuple)):
            raise ValueError("DiagnosticArray.status must be a sequence")

        limitations = []
        components = []
        entries = []
        ignored_keys = []
        for status_index, status in enumerate(statuses):
            component = _get(status, "name")
            if component not in (None, "") and str(component) not in components:
                components.append(str(component))
            values = _get(status, "values", ())
            if values is None:
                values = ()
            try:
                values = list(values)
            except TypeError:
                limitations.append(f"Diagnostic status {status_index} has malformed values; skipped.")
                continue
            for value_index, pair in enumerate(values):
                key = _get(pair, "key")
                value = _get(pair, "value")
                if not isinstance(key, str) or not key:
                    limitations.append(
                        f"Diagnostic KeyValue at status {status_index}, index {value_index} has no valid key; skipped."
                    )
                    continue
                entries.append((key, value))

        units_by_key = defaultdict(list)
        for key, value in entries:
            target = self._unit_target(key)
            if target:
                units_by_key[key[:-5]].append(str(value).strip())

        candidates = defaultdict(list)
        source_keys = defaultdict(list)
        unit_sources = {}
        known_unit_keys = {key for key, _value in entries if self._unit_target(key)}
        for key, value in entries:
            if key in known_unit_keys:
                continue
            target = self.key_mappings.get(key)
            if target is None:
                ignored_keys.append(key)
                continue
            if key not in source_keys[target]:
                source_keys[target].append(key)
            if target == "robot_state":
                normalized, error = self._normalize_state(value)
                candidates[target].append((normalized, error, key))
                continue

            declared_units = list(units_by_key.get(key, ()))
            for companion in (f"{key}_unit", f"{target}_unit"):
                declared_units.extend(units_by_key.get(companion[:-5], ()))
            if len({unit.strip().lower() for unit in declared_units}) > 1:
                candidates[target].append((None, "conflicting unit declarations", key))
                continue
            unit = declared_units[0] if declared_units else self.field_units.get(target)
            numeric, embedded_unit, error = self._parse_numeric(value)
            if error:
                candidates[target].append((None, error, key))
                continue
            if embedded_unit and unit and self._unit_name(target, embedded_unit) != self._unit_name(target, unit):
                candidates[target].append((None, "conflicting inline and diagnostic units", key))
                continue
            unit = embedded_unit or unit
            converted, canonical_unit, error = self._convert(target, numeric, unit)
            candidates[target].append((converted, error, key))
            if not error:
                unit_sources[target] = canonical_unit

        telemetry = {}
        for field, values in candidates.items():
            invalid = [candidate for candidate in values if candidate[1] is not None]
            valid_values = [candidate[0] for candidate in values if candidate[1] is None]
            if invalid:
                reasons = sorted({candidate[1] for candidate in invalid})
                limitations.append(f"{field} unavailable: " + "; ".join(reasons) + ".")
                continue
            if not valid_values:
                continue
            if any(not math.isclose(valid_values[0], item, rel_tol=0.0, abs_tol=1e-9)
                   for item in valid_values[1:]):
                limitations.append(f"{field} unavailable: conflicting duplicate diagnostic values.")
                continue
            telemetry[field] = valid_values[0]

        timestamp, timestamp_step = self._timestamp(diagnostic_array)
        if time_step is not None:
            if isinstance(time_step, bool) or not isinstance(time_step, Real) or not math.isfinite(float(time_step)):
                raise ValueError("time_step must be a finite number")
            timestamp_step = time_step
        if timestamp_step is not None:
            telemetry["time_step"] = timestamp_step
        elif timestamp is None:
            limitations.append("Timestamp unavailable; Genesis may assign an ingestion-order time step.")
        else:
            limitations.append(
                "Timestamp preserved but not convertible to a numeric time_step; "
                "Genesis may assign an ingestion-order time step."
            )

        if not statuses:
            limitations.append("DiagnosticArray contains no statuses.")
        elif not entries:
            limitations.append("DiagnosticArray contains no KeyValue telemetry.")
        if ignored_keys:
            limitations.append(
                "Unmapped diagnostic keys ignored: " + ", ".join(dict.fromkeys(ignored_keys)) + "."
            )

        return {
            "identity": dict(self.identity),
            "telemetry": telemetry,
            "source": "ros2",
            "source_metadata": {
                "source": "ros2",
                "diagnostic_components": components,
                "source_keys": dict(source_keys),
                "units": unit_sources,
                "timestamp": timestamp,
                "ignored_keys": list(dict.fromkeys(ignored_keys)),
            },
            "limitations": limitations,
        }

    def ingest(self, diagnostic_array, *, time_step=None):
        """Alias for ``adapt`` when processing a live message stream."""
        return self.adapt(diagnostic_array, time_step=time_step)

    def _unit_target(self, key):
        if not key.endswith("_unit"):
            return None
        return self.key_mappings.get(key[:-5])

    @staticmethod
    def _parse_numeric(value):
        if isinstance(value, bool) or value is None:
            return None, None, "malformed numeric value"
        if isinstance(value, Real):
            numeric = float(value)
            return (numeric, None, None) if math.isfinite(numeric) else (None, None, "non-finite numeric value")
        match = _NUMBER_WITH_UNIT.fullmatch(str(value))
        if not match:
            return None, None, "malformed numeric value"
        try:
            numeric = float(match.group(1))
        except (TypeError, ValueError):
            return None, None, "malformed numeric value"
        if not math.isfinite(numeric):
            return None, None, "non-finite numeric value"
        unit = match.group(2)
        return numeric, unit.strip() if unit else None, None

    @staticmethod
    def _normalize_state(value):
        state = str(value).strip().lower() if value is not None else ""
        if state in _STATE_ALIASES:
            return _STATE_ALIASES[state], None
        return None, "unsupported robot state"

    @staticmethod
    def _unit_name(field, unit):
        category = _NUMERIC_UNITS[field]
        if unit is None:
            return None
        return _UNIT_ALIASES[category].get(str(unit).strip().lower())

    def _convert(self, field, value, unit):
        category = _NUMERIC_UNITS[field]
        canonical = self._unit_name(field, unit)
        if canonical is None:
            return None, None, "missing or unsupported unit"
        if category == "temperature":
            if canonical == "F":
                value = (value - 32.0) * 5.0 / 9.0
            elif canonical == "K":
                value -= 273.15
            canonical = "C"
        elif category == "percentage":
            if not 0.0 <= value <= 100.0:
                return None, None, "percentage outside Genesis 0–100 convention"
        return float(value), canonical, None

    @staticmethod
    def _timestamp(message):
        header = _get(message, "header")
        stamp = _get(header, "stamp") if header is not None else None
        if stamp is None:
            timestamp = _get(message, "timestamp")
            if isinstance(timestamp, Real) and not isinstance(timestamp, bool):
                if math.isfinite(float(timestamp)):
                    return timestamp, timestamp
            return _json_value(timestamp), None

        sec = _get(stamp, "sec")
        nanosec = _get(stamp, "nanosec", _get(stamp, "nsec"))
        if sec is not None and nanosec is not None:
            seconds = float(sec) + float(nanosec) / 1_000_000_000.0
            return {"sec": int(sec), "nanosec": int(nanosec)}, seconds
        if isinstance(stamp, Real) and not isinstance(stamp, bool) and math.isfinite(float(stamp)):
            return stamp, stamp
        return _json_value(stamp), None
