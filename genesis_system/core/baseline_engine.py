BASELINE_ELIGIBLE = "ELIGIBLE"
BASELINE_INELIGIBLE = "INELIGIBLE"
BASELINE_UNKNOWN = "UNKNOWN"


class RoboticsBaselineEligibilityPolicy:
    """Decide whether a robot record is an approved baseline reference.

    Explicit decisions support external telemetry without treating absent
    simulator fields as evidence of health. Legacy simulator records retain
    their previous eligibility rule.
    """

    def is_eligible(self, record):
        if not isinstance(record, dict):
            return False

        # Failure observations remain excluded even if a caller accidentally
        # marks them eligible. Missing failure_event is not itself approval.
        if record.get("robot_state") == "failed" or record.get("failure_event", False):
            return False

        if "baseline_eligibility" in record:
            decision = record.get("baseline_eligibility")
            if decision != BASELINE_ELIGIBLE:
                return False

            quality = record.get("observation_quality")
            if isinstance(quality, dict):
                if quality.get("status") not in (None, "AVAILABLE"):
                    return False
                groups = quality.get("groups") or {}
                if any(
                    group.get("status") != "AVAILABLE"
                    for group in groups.values()
                    if isinstance(group, dict)
                ):
                    return False
            return True

        # Backward-compatible simulator path. Records without an explicit
        # decision and without simulator health are conservatively unknown.
        return (
            record.get("health") == "healthy"
            and record.get("robot_state") != "failed"
            and not record.get("failure_event", False)
        )


class BaselineEngine:

    def __init__(self, minimum_records=10, eligibility_policy=None):
        self.minimum_records = minimum_records
        self.eligibility_policy = (
            eligibility_policy
            if eligibility_policy is not None
            else RoboticsBaselineEligibilityPolicy()
        )

    def build_baseline(self, historical_records):

        eligible_records = [
            record
            for record in historical_records
            if self.eligibility_policy.is_eligible(record)
        ]

        if len(eligible_records) < self.minimum_records:
            return {
                "status": "insufficient_data",
                "message": (
                    f"Need at least {self.minimum_records} "
                    "eligible records to establish a baseline."
                ),
                "records_used": len(eligible_records),
                "metrics": {}
            }

        motor_temperatures = [
            record["motor_temperature"]
            for record in eligible_records
            if record.get("motor_temperature") is not None
        ]

        thermal_rises = [
            record["thermal_rise"]
            for record in eligible_records
            if record.get("thermal_rise") is not None
        ]

        battery_levels = [
            record["battery_level"]
            for record in eligible_records
            if record.get("battery_level") is not None
        ]

        metrics = {}

        if motor_temperatures:
            metrics["average_motor_temperature"] = round(
                sum(motor_temperatures) / len(motor_temperatures),
                2
            )

        if thermal_rises:
            metrics["average_thermal_rise"] = round(
                sum(thermal_rises) / len(thermal_rises),
                2
            )

        if battery_levels:
            metrics["average_battery_level"] = round(
                sum(battery_levels) / len(battery_levels),
                2
            )

        return {
            "status": "baseline_available",
            "records_used": len(eligible_records),
            "metrics": metrics
        }
