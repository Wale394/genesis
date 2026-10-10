class BaselineEngine:

    def __init__(self, minimum_records=10):
        self.minimum_records = minimum_records

    def build_baseline(self, historical_records):

        healthy_records = [
            record
            for record in historical_records
            if record.get("health") == "healthy"
            and record.get("robot_state") != "failed"
            and not record.get("failure_event", False)
        ]

        if len(healthy_records) < self.minimum_records:
            return {
                "status": "insufficient_data",
                "message": (
                    f"Need at least {self.minimum_records} "
                    "healthy records to establish a baseline."
                ),
                "records_used": len(healthy_records),
                "metrics": {}
            }

        motor_temperatures = [
            record["motor_temperature"]
            for record in healthy_records
            if record.get("motor_temperature") is not None
        ]

        thermal_rises = [
            record["thermal_rise"]
            for record in healthy_records
            if record.get("thermal_rise") is not None
        ]

        battery_levels = [
            record["battery_level"]
            for record in healthy_records
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
            "records_used": len(healthy_records),
            "metrics": metrics
        }