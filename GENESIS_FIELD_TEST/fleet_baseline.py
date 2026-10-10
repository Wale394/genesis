"""Deterministic peer baselines for observable fleet telemetry."""

from collections import defaultdict
from copy import deepcopy
import math
from numbers import Real
import statistics


FLEET_COMPARISON = "FLEET_COMPARISON"

# These are contextual statistical thresholds, not physical safety limits.
MINIMUM_PEER_COUNT = 2
ELEVATED_Z_THRESHOLD = 1.0
OUTLIER_Z_THRESHOLD = 2.0
ZERO_VARIANCE_EPSILON = 1e-9
ROUND_DIGITS = 3

METRICS = (
    "motor_temperature", "ambient_temperature", "thermal_rise",
    "battery_level", "battery_voltage", "battery_current",
    "battery_temperature", "power_consumption", "voltage_drop", "workload",
)

_QUALITY_GROUP = {
    "motor_temperature": "thermal", "ambient_temperature": "thermal",
    "thermal_rise": "thermal", "battery_level": "battery",
    "battery_voltage": "battery", "battery_current": "battery",
    "battery_temperature": "battery", "voltage_drop": "battery",
    "power_consumption": "workload", "workload": "workload",
}


def _number(value):
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _round(value):
    return round(float(value), ROUND_DIGITS) if value is not None else None


class FleetBaseline:
    """Group comparable robots and calculate explainable peer context.

    ``add_observation`` keeps only the latest and previous snapshot per robot.
    No simulator-only field is read or retained.
    """

    def __init__(self, minimum_peer_count=MINIMUM_PEER_COUNT):
        if minimum_peer_count < 2:
            raise ValueError("minimum_peer_count must be at least 2")
        self.minimum_peer_count = minimum_peer_count
        self._latest = {}
        self._previous = {}

    def add_observation(self, record, observation_quality=None):
        robot_id = record.get("robot_id")
        if not robot_id:
            return False
        snapshot = {
            key: record.get(key)
            for key in (
                "robot_id", "manufacturer", "robot_type", "time_step", *METRICS,
            )
        }
        snapshot["_quality"] = deepcopy(observation_quality or {})
        robot_id = str(robot_id)
        if robot_id in self._latest:
            self._previous[robot_id] = self._latest[robot_id]
        self._latest[robot_id] = snapshot
        return True

    def compare(
        self,
        current_record,
        peer_records=None,
        observation_quality=None,
        previous_peer_records=None,
    ):
        """Compare an observation to the latest eligible observation per peer."""
        current = {
            key: current_record.get(key)
            for key in ("robot_id", "manufacturer", "robot_type", "time_step", *METRICS)
        }
        supplied = self._latest.values() if peer_records is None else peer_records
        peers = self._eligible_peers(current, supplied)
        group, group_level = self._peer_group(current)
        prior_source = self._previous.values() if previous_peer_records is None else previous_peer_records
        previous_peers = self._eligible_peers(current, prior_source)

        metrics = {}
        for metric in METRICS:
            metrics[metric] = self._compare_metric(
                metric, current, peers, previous_peers, observation_quality or {}
            )

        patterns = {item["pattern"] for item in metrics.values()}
        if "robot_specific" in patterns:
            fleet_pattern = "robot_specific"
        elif "peer_wide" in patterns:
            fleet_pattern = "peer_wide"
        elif any(item["status"] != "INSUFFICIENT_DATA" for item in metrics.values()):
            fleet_pattern = "no_peer_deviation"
        else:
            fleet_pattern = "insufficient_data"

        usable = sum(item["status"] != "INSUFFICIENT_DATA" for item in metrics.values())
        return {
            "status": "AVAILABLE" if usable else "INSUFFICIENT_DATA",
            "type": FLEET_COMPARISON,
            "robot_id": current.get("robot_id"),
            "peer_group": group,
            "peer_group_level": group_level,
            "comparable_robot_count": len(peers),
            "minimum_peer_count": self.minimum_peer_count,
            "fleet_pattern": fleet_pattern,
            "metrics": metrics,
            "limitations": self._group_limitations(current, peers),
            "message": None if usable else "Fleet comparison unavailable: insufficient comparable robots or usable telemetry.",
        }

    def _peer_group(self, current):
        robot_type = current.get("robot_type")
        manufacturer = current.get("manufacturer")
        if not robot_type:
            return None, "unavailable"
        if manufacturer:
            return {"manufacturer": manufacturer, "robot_type": robot_type}, "manufacturer_and_type"
        return {"robot_type": robot_type}, "robot_type"

    def _eligible_peers(self, current, records):
        if not current.get("robot_type"):
            return []
        latest = {}
        for position, record in enumerate(records or []):
            if not isinstance(record, dict):
                continue
            robot_id = record.get("robot_id")
            if not robot_id or str(robot_id) == str(current.get("robot_id")):
                continue
            if record.get("robot_type") != current.get("robot_type"):
                continue
            manufacturer = current.get("manufacturer")
            if manufacturer and record.get("manufacturer") != manufacturer:
                continue
            # Input order is chronological by convention; keep one sample per robot.
            latest[str(robot_id)] = (position, record)
        return [deepcopy(value[1]) for value in latest.values()]

    def _group_limitations(self, current, peers):
        if not current.get("robot_type"):
            return ["robot_type unavailable; comparable peer group cannot be formed"]
        if len(peers) < self.minimum_peer_count:
            return [
                f"only {len(peers)} comparable peer(s); at least {self.minimum_peer_count} required"
            ]
        return []

    def _compare_metric(self, metric, current, peers, previous_peers, current_quality):
        field_group = _QUALITY_GROUP[metric]
        current_group_quality = (current_quality.get("groups") or {}).get(field_group, {})
        missing_ids = []
        invalid_ids = []
        degraded_ids = []
        values = []
        for peer in peers:
            robot_id = str(peer.get("robot_id"))
            value = peer.get(metric)
            quality = peer.get("_quality") or peer.get("observation_quality") or {}
            group_quality = (quality.get("groups") or {}).get(field_group, {})
            if value is None:
                missing_ids.append(robot_id)
            elif not _number(value):
                invalid_ids.append(robot_id)
            elif group_quality and group_quality.get("status") != "AVAILABLE":
                degraded_ids.append(robot_id)
            else:
                values.append(float(value))

        current_value = current.get(metric)
        reasons = []
        if current_group_quality and current_group_quality.get("status") != "AVAILABLE":
            reasons.append("current_observation_quality_" + str(current_group_quality.get("status", "unknown")).lower())
        if current_value is None:
            reasons.append("current_metric_missing")
        elif not _number(current_value):
            reasons.append("current_metric_invalid")
        if missing_ids:
            reasons.append("peer_values_missing")
        if invalid_ids:
            reasons.append("peer_values_invalid")
        if degraded_ids:
            reasons.append("peer_observation_quality_degraded")
        if len(peers) < self.minimum_peer_count:
            reasons.append("insufficient_peer_count")

        complete = not reasons and len(values) == len(peers) and len(peers) >= self.minimum_peer_count
        baseline = None
        z_score = None
        deviation = None
        status = "INSUFFICIENT_DATA"
        if complete:
            mean = statistics.mean(values)
            std = statistics.stdev(values) if len(values) >= 2 else None
            deviation = float(current_value) - mean
            if std is None or std <= ZERO_VARIANCE_EPSILON:
                z_score = 0.0 if abs(deviation) <= ZERO_VARIANCE_EPSILON else None
                status = "NORMAL" if z_score == 0.0 else "OUTLIER"
                if z_score is None:
                    reasons.append("peer_variance_zero_z_score_unavailable")
            else:
                z_score = deviation / std
                absolute_z = abs(z_score)
                status = (
                    "OUTLIER" if absolute_z >= OUTLIER_Z_THRESHOLD else
                    "ELEVATED" if z_score >= ELEVATED_Z_THRESHOLD else
                    "NORMAL"
                )
            baseline = {
                "peer_count": len(values),
                "mean": _round(mean),
                "median": _round(statistics.median(values)),
                "minimum": _round(min(values)),
                "maximum": _round(max(values)),
                "standard_deviation": _round(std) if std is not None else 0.0,
            }

        temporal = self._peer_temporal_shift(metric, peers, previous_peers)
        if status != "OUTLIER" and temporal and temporal["status"] == "peer_wide":
            pattern = "peer_wide"
        elif status == "OUTLIER":
            pattern = "robot_specific"
        elif status == "INSUFFICIENT_DATA":
            pattern = "insufficient_data"
        else:
            pattern = "no_peer_deviation"

        if status == "OUTLIER" and baseline:
            position = "above" if deviation > 0 else "below"
            interpretation = (
                f"Observed {metric} is {position} the range of comparable peers."
            )
        elif pattern == "peer_wide" and temporal:
            interpretation = (
                f"Comparable peers show a shared {temporal['direction']} change in {metric}."
            )
        elif status == "ELEVATED":
            interpretation = f"Observed {metric} is elevated relative to the comparable-peer mean."
        elif status == "NORMAL":
            interpretation = f"Observed {metric} is within the contextual range of comparable peers."
        else:
            interpretation = f"Peer comparison for {metric} is unavailable or insufficient."

        result = {
            "type": FLEET_COMPARISON,
            "metric": metric,
            "robot_value": float(current_value) if _number(current_value) else None,
            "peer_count": len(values),
            "expected_peer_count": len(peers),
            "peer_mean": baseline["mean"] if baseline else None,
            "peer_median": baseline["median"] if baseline else None,
            "peer_minimum": baseline["minimum"] if baseline else None,
            "peer_maximum": baseline["maximum"] if baseline else None,
            "peer_standard_deviation": baseline["standard_deviation"] if baseline else None,
            "deviation": _round(deviation),
            "z_score": _round(z_score),
            "status": status,
            "pattern": pattern,
            "interpretation": interpretation,
            "quality": "DEGRADED" if reasons else "AVAILABLE",
            "missing_peer_ids": missing_ids,
            "invalid_peer_ids": invalid_ids,
            "degraded_peer_ids": degraded_ids,
            "limitations": reasons,
            "temporal_context": temporal,
        }
        return result

    def _peer_temporal_shift(self, metric, peers, previous_peers):
        if not peers or not previous_peers:
            return {"status": "UNAVAILABLE", "reason": "previous peer observations unavailable"}
        prior = {str(item.get("robot_id")): item for item in previous_peers}
        changes = []
        previous_values = []
        for peer in peers:
            robot_id = str(peer.get("robot_id"))
            old = prior.get(robot_id)
            if old is None or not _number(peer.get(metric)) or not _number(old.get(metric)):
                continue
            changes.append(float(peer[metric]) - float(old[metric]))
            previous_values.append(float(old[metric]))
        if len(changes) < self.minimum_peer_count:
            return {"status": "UNAVAILABLE", "reason": "insufficient paired peer history"}
        mean_change = statistics.mean(changes)
        scale = statistics.stdev(previous_values) if len(previous_values) > 1 else 0.0
        standardized_change = (
            abs(mean_change) / scale if scale > ZERO_VARIANCE_EPSILON
            else (float("inf") if abs(mean_change) > ZERO_VARIANCE_EPSILON else 0.0)
        )
        majority_aligned = sum(change > 0 for change in changes) >= math.ceil(len(changes) * 0.75) or sum(
            change < 0 for change in changes
        ) >= math.ceil(len(changes) * 0.75)
        peer_wide = majority_aligned and standardized_change >= ELEVATED_Z_THRESHOLD
        return {
            "status": "peer_wide" if peer_wide else "no_peer_wide_shift",
            "paired_peer_count": len(changes),
            "previous_peer_mean": _round(statistics.mean(previous_values)),
            "current_peer_mean": _round(statistics.mean([float(peer[metric]) for peer in peers if _number(peer.get(metric))])),
            "mean_change": _round(mean_change),
            "direction": "increasing" if mean_change > 0 else "decreasing" if mean_change < 0 else "stable",
            "standardized_change": None if not math.isfinite(standardized_change) else _round(standardized_change),
            "limitations": [],
        }
