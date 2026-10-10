from collections import defaultdict

from feature_contract import (
    HISTORY_COUNT_FIELD,
    build_features,
)


class TelemetryFeatureBuilder:
    """Stateful streaming wrapper around the shared feature contract."""

    def __init__(self):
        self.history = defaultdict(list)

    def build(self, telemetry_snapshot):
        telemetry = telemetry_snapshot["telemetry"]
        identity = telemetry_snapshot["identity"]
        robot_id = identity["robot_id"]

        current = {
            "robot_id": robot_id,
            "manufacturer": identity.get("manufacturer"),
            "robot_type": identity.get("robot_type"),
            "time_step": telemetry["time_step"],
        }
        for field in (
            "motor_temperature",
            "ambient_temperature",
            "battery_level",
            "battery_voltage",
            "battery_current",
            "battery_temperature",
            "power_consumption",
            "voltage_drop",
            "robot_state",
            "workload",
        ):
            current[field] = telemetry.get(field)

        robot_history = self.history[robot_id]
        feature_record = dict(current)
        feature_record.update(build_features(current, robot_history))
        feature_record[HISTORY_COUNT_FIELD] = len(robot_history)

        # An external robot does not provide simulator ground truth.
        feature_record.update({
            "failure_event": None,
            "recovery_event": None,
            "failure_type": None,
        })

        robot_history.append(current)
        return feature_record

    def get_available_features(self, feature_record):
        available = []
        unavailable = []
        for key, value in feature_record.items():
            (unavailable if value is None else available).append(key)
        return {"available": available, "unavailable": unavailable}
