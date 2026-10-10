"""Deterministic descriptions of observable telemetry trajectories.

Patterns here describe measurements only. They are not failure predictions,
diagnoses, causal claims, or recommendations.
"""

from copy import deepcopy
from math import isfinite

from feature_contract import build_features


# All detector thresholds live here. They are deterministic, fleet-wide
# defaults expressed as observed changes, ratios, or within-window comparisons;
# they are not learned or robot-specific physical limits.
PATTERN_THRESHOLDS = {
    "window_size": 10,
    "minimum_observations": 5,
    "sustained_net_rise": 2.0,
    "sustained_positive_fraction": 0.60,
    "volatile_minimum_net_rise": 0.5,
    "volatile_max_net_to_path_ratio": 0.35,
    "minimum_direction_changes": 2,
    "rapid_spike_delta": 5.0,
    "repeated_spike_delta": 4.0,
    "minimum_repeated_spikes": 2,
    "persistent_elevation_margin": 3.0,
    "persistent_elevation_observations": 3,
    "battery_level_net_decline": 3.0,
    "battery_voltage_net_decline": 0.2,
    "battery_decline_negative_fraction": 0.60,
    "voltage_instability_delta": 0.10,
    "voltage_instability_changes_each_direction": 2,
    "workload_high_quantile": 0.75,
    "thermal_workload_coobservations": 2,
}

_THERMAL_FIELDS = ("motor_temperature", "thermal_rise")
_BATTERY_FIELDS = ("battery_level", "battery_voltage")
_WORKLOAD_FIELDS = ("workload",)
_IGNORED_FIELDS = frozenset({
    "failure_event", "failure_type", "recovery_event", "label",
    "failure_type_label", "health", "initial_health", "battery_health",
    "battery_stress", "degradation_level",
})


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _json_time(value):
    numeric = _number(value)
    if numeric is not None:
        return int(numeric) if numeric.is_integer() else numeric
    return str(value) if value is not None else None


def _ordered_records(records):
    """Sort by numeric time_step when all rows have one; otherwise keep order."""
    indexed = list(enumerate(records or ()))
    if not indexed:
        return []
    try:
        indexed.sort(key=lambda item: (float(item[1]["time_step"]), item[0]))
    except (KeyError, TypeError, ValueError):
        pass
    return [record for _index, record in indexed]


def _quantile(values, quantile):
    """Deterministic nearest-rank quantile (no third-party dependency)."""
    ordered = sorted(values)
    if not ordered:
        return None
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * quantile + 0.999999)))
    return ordered[index]


class TelemetryPatternEngine:
    """Identify deterministic temporal patterns in one robot's telemetry."""

    def __init__(self, thresholds=None):
        self.thresholds = dict(PATTERN_THRESHOLDS)
        if thresholds:
            unknown = set(thresholds) - set(PATTERN_THRESHOLDS)
            if unknown:
                raise ValueError("Unknown pattern thresholds: " + ", ".join(sorted(unknown)))
            self.thresholds.update(thresholds)

    def analyze(self, records):
        ordered = _ordered_records(records)
        window_size = int(self.thresholds["window_size"])
        window = ordered[-window_size:]
        result = {
            "status": "available",
            "window_size": window_size,
            "observations_analyzed": len(window),
            "patterns": [],
            "limitations": [],
        }

        minimum = int(self.thresholds["minimum_observations"])
        if len(window) < minimum:
            result["status"] = "insufficient_data"
            result["limitations"].append(
                f"At least {minimum} chronological observations are required; "
                f"received {len(window)}."
            )
            return result

        # Ask the canonical feature contract for derived values. Existing
        # supplied feature values take precedence, while raw telemetry is
        # enriched with the same shared temporal definitions.
        enriched = []
        raw_history = []
        for record in window:
            raw = {key: value for key, value in record.items() if key not in _IGNORED_FIELDS}
            contract_features = build_features(raw, raw_history)
            merged = dict(raw)
            for key, value in contract_features.items():
                if merged.get(key) is None:
                    merged[key] = value
            # thermal_rise is canonical motor minus ambient when possible;
            # preserve a supplied deployable derived value if raw inputs are
            # unavailable.
            if merged.get("thermal_rise") is None:
                merged["thermal_rise"] = contract_features.get("thermal_rise")
            enriched.append(merged)
            raw_history.append(raw)

        thermal_field = next(
            (field for field in _THERMAL_FIELDS
             if sum(_number(row.get(field)) is not None for row in enriched) >= minimum),
            None,
        )
        if thermal_field is None:
            result["limitations"].append(
                "No thermal measurement has enough numeric observations for temporal patterns."
            )
        else:
            thermal_values = [_number(row.get(thermal_field)) for row in enriched]
            changes = self._changes(enriched, thermal_field)
            evidence = self._evidence(enriched, (thermal_field, "ambient_temperature", "workload"))
            self._analyze_thermal(
                result["patterns"], thermal_field, thermal_values, changes,
                evidence, enriched,
            )

        self._analyze_battery(result, enriched)
        if not any(row.get(field) is not None for row in enriched for field in _WORKLOAD_FIELDS):
            result["limitations"].append("Workload telemetry is unavailable.")
        has_battery = any(
            sum(_number(row.get(field)) is not None for row in enriched) >= minimum
            for field in _BATTERY_FIELDS
        )
        if thermal_field is None and not has_battery:
            result["status"] = "insufficient_data"
        return result

    def _changes(self, rows, field):
        changes = []
        for index in range(1, len(rows)):
            current = _number(rows[index].get(field))
            previous = _number(rows[index - 1].get(field))
            if current is None or previous is None:
                continue
            # Use the shared contract's one-step feature when present; this is
            # current minus previous, with the same rounding policy.
            supplied_name = {
                "motor_temperature": "temperature_change",
                "battery_level": "battery_change",
                "battery_voltage": "battery_voltage_change",
            }.get(field)
            supplied = _number(rows[index].get(supplied_name)) if supplied_name else None
            delta = supplied if supplied is not None else round(current - previous, 2)
            changes.append({
                "from_index": index - 1,
                "to_index": index,
                "from_time_step": _json_time(rows[index - 1].get("time_step")),
                "to_time_step": _json_time(rows[index].get("time_step")),
                "delta": delta,
            })
        return changes

    @staticmethod
    def _evidence(rows, fields):
        evidence = []
        for row in rows:
            measurement = {}
            if row.get("time_step") is not None:
                measurement["time_step"] = _json_time(row.get("time_step"))
            for field in fields:
                value = _number(row.get(field))
                if value is not None:
                    measurement[field] = value
            evidence.append(measurement)
        return evidence

    def _add(self, patterns, name, domain, observations, metrics, description):
        patterns.append({
            "pattern": name,
            "domain": domain,
            "observations": deepcopy(observations),
            "metrics": metrics,
            "description": description,
        })

    def _analyze_thermal(self, patterns, field, values, changes, evidence, rows):
        present = [value for value in values if value is not None]
        if len(present) < int(self.thresholds["minimum_observations"]):
            return
        first, last = present[0], present[-1]
        net = round(last - first, 2)
        positive = [item for item in changes if item["delta"] > 0]
        negative = [item for item in changes if item["delta"] < 0]
        direction_count = len(positive) + len(negative)
        positive_fraction = len(positive) / direction_count if direction_count else 0.0
        total_path = sum(abs(item["delta"]) for item in changes)
        net_ratio = abs(net) / total_path if total_path else 0.0
        reversals = sum(
            changes[index]["delta"] * changes[index - 1]["delta"] < 0
            for index in range(1, len(changes))
        )

        if (net >= self.thresholds["sustained_net_rise"]
                and positive_fraction >= self.thresholds["sustained_positive_fraction"]):
            self._add(patterns, "SUSTAINED_RISE", "thermal", evidence, {
                "measurement": field, "net_increase": net,
                "positive_change_count": len(positive),
                "negative_change_count": len(negative),
                "positive_change_fraction": round(positive_fraction, 3),
                "changes": deepcopy(changes),
            }, f"{field} increased across the analyzed window with predominantly positive step changes.")

        if (net >= self.thresholds["volatile_minimum_net_rise"]
                and len(positive) >= self.thresholds["minimum_direction_changes"]
                and len(negative) >= self.thresholds["minimum_direction_changes"]
                and reversals >= self.thresholds["minimum_direction_changes"]
                and net_ratio <= self.thresholds["volatile_max_net_to_path_ratio"]):
            self._add(patterns, "VOLATILE_RISE", "thermal", evidence, {
                "measurement": field, "net_increase": net,
                "total_absolute_step_change": round(total_path, 2),
                "net_to_path_ratio": round(net_ratio, 3),
                "positive_change_count": len(positive),
                "negative_change_count": len(negative),
                "direction_reversals": reversals,
                "changes": deepcopy(changes),
            }, f"{field} increased overall while repeatedly reversing direction.")

        spikes = [item for item in changes if item["delta"] >= self.thresholds["rapid_spike_delta"]]
        if spikes:
            spike = max(spikes, key=lambda item: item["delta"])
            self._add(patterns, "RAPID_SPIKE", "thermal", evidence, {
                "measurement": field, "observed_delta": spike["delta"],
                "from_time_step": spike["from_time_step"],
                "to_time_step": spike["to_time_step"],
                "configured_delta_threshold": self.thresholds["rapid_spike_delta"],
                "qualifying_spike_count": len(spikes),
            }, f"{field} increased by {spike['delta']:.2f} in one observed step.")

        repeated = [item for item in changes if item["delta"] >= self.thresholds["repeated_spike_delta"]]
        separated = []
        for spike in repeated:
            if separated and not any(
                item["delta"] < 0
                and separated[-1]["to_index"] < item["to_index"] < spike["to_index"]
                for item in changes
            ):
                continue
            separated.append(spike)
        if len(separated) >= self.thresholds["minimum_repeated_spikes"]:
            self._add(patterns, "REPEATED_SPIKES", "thermal", evidence, {
                "measurement": field,
                "spike_deltas": [item["delta"] for item in separated],
                "spike_time_steps": [item["to_time_step"] for item in separated],
                "configured_delta_threshold": self.thresholds["repeated_spike_delta"],
                "intervening_declines_observed": True,
            }, f"Multiple significant positive {field} changes were separated by observed declines.")

        # Elevation is relative to this window's first half, avoiding an
        # absolute temperature limit shared across different robot designs.
        half = max(1, len(values) // 2)
        baseline = [value for value in values[:half] if value is not None]
        if baseline:
            elevation_threshold = statistics_median(baseline) + self.thresholds["persistent_elevation_margin"]
            trailing = 0
            for value in reversed(values):
                if value is not None and value >= elevation_threshold:
                    trailing += 1
                else:
                    break
            if trailing >= self.thresholds["persistent_elevation_observations"]:
                self._add(patterns, "PERSISTENT_ELEVATION", "thermal", evidence, {
                    "measurement": field,
                    "baseline_median": round(statistics_median(baseline), 2),
                    "relative_elevation_threshold": round(elevation_threshold, 2),
                    "consecutive_elevated_observations": trailing,
                    "configured_baseline_margin": self.thresholds["persistent_elevation_margin"],
                }, f"{field} remained above its first-half baseline by the configured margin for {trailing} consecutive observations.")

        workloads = [_number(row.get("workload")) for row in rows]
        known_workloads = [value for value in workloads if value is not None]
        if known_workloads and baseline:
            high_workload = _quantile(known_workloads, self.thresholds["workload_high_quantile"])
            elevated_threshold = statistics_median(baseline) + self.thresholds["persistent_elevation_margin"]
            paired = [
                index for index, (value, workload) in enumerate(zip(values, workloads))
                if value is not None and workload is not None
                and value >= elevated_threshold and workload >= high_workload
            ]
            if len(paired) >= self.thresholds["thermal_workload_coobservations"]:
                self._add(patterns, "THERMAL_WITH_HIGH_WORKLOAD", "thermal_workload", evidence, {
                    "thermal_measurement": field,
                    "relative_elevation_threshold": round(elevated_threshold, 2),
                    "workload_high_threshold": round(high_workload, 2),
                    "coobserved_indices": paired,
                    "coobservation_count": len(paired),
                }, "Elevated thermal measurements coincided with higher workload observations; this is an association only.")

    def _analyze_battery(self, result, rows):
        minimum = int(self.thresholds["minimum_observations"])
        for field, threshold in (
            ("battery_level", self.thresholds["battery_level_net_decline"]),
            ("battery_voltage", self.thresholds["battery_voltage_net_decline"]),
        ):
            values = [_number(row.get(field)) for row in rows]
            present = [value for value in values if value is not None]
            if len(present) < minimum:
                continue
            changes = self._changes(rows, field)
            declines = [item for item in changes if item["delta"] < 0]
            directions = [item for item in changes if item["delta"] != 0]
            decline_fraction = len(declines) / len(directions) if directions else 0.0
            net_decline = round(present[0] - present[-1], 2)
            if net_decline >= threshold and decline_fraction >= self.thresholds["battery_decline_negative_fraction"]:
                self._add(result["patterns"], "DECLINING_BATTERY", "battery", self._evidence(rows, (field,)), {
                    "measurement": field,
                    "net_decline": net_decline,
                    "negative_change_count": len(declines),
                    "nonzero_change_count": len(directions),
                    "negative_change_fraction": round(decline_fraction, 3),
                    "changes": deepcopy(changes),
                    "configured_net_decline_threshold": threshold,
                }, f"{field} declined across the analyzed window with predominantly negative step changes.")

        voltages = [_number(row.get("battery_voltage")) for row in rows]
        if sum(value is not None for value in voltages) >= minimum:
            changes = self._changes(rows, "battery_voltage")
            meaningful = [item for item in changes if abs(item["delta"]) >= self.thresholds["voltage_instability_delta"]]
            positive = [item for item in meaningful if item["delta"] > 0]
            negative = [item for item in meaningful if item["delta"] < 0]
            each = self.thresholds["voltage_instability_changes_each_direction"]
            if len(positive) >= each and len(negative) >= each:
                self._add(result["patterns"], "VOLTAGE_INSTABILITY", "battery", self._evidence(rows, ("battery_voltage",)), {
                    "positive_meaningful_change_count": len(positive),
                    "negative_meaningful_change_count": len(negative),
                    "meaningful_change_threshold": self.thresholds["voltage_instability_delta"],
                    "changes": deepcopy(changes),
                }, "Battery voltage showed repeated meaningful changes in both directions.")


def statistics_median(values):
    """Small local median helper so the engine has no added dependencies."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2
