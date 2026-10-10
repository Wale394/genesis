class ComparisonEngine:

    def __init__(self, history_window=10):
        self.history_window = history_window

    def compare_to_history(self, current_record, historical_records):
        if not historical_records:
            return {
                "status": "insufficient_data",
                "message": "Not enough historical data for comparison.",
                "metrics": {}
            }

        recent_records = historical_records[-self.history_window:]

        current_temperature = current_record.get("motor_temperature")
        current_thermal_rise = current_record.get("thermal_rise")

        historical_temperatures = [
            record.get("motor_temperature")
            for record in recent_records
            if record.get("motor_temperature") is not None
        ]

        historical_thermal_rises = [
            record.get("thermal_rise")
            for record in recent_records
            if record.get("thermal_rise") is not None
        ]

        metrics = {}

        if historical_temperatures and current_temperature is not None:
            average_temperature = (
                sum(historical_temperatures)
                / len(historical_temperatures)
            )

            temperature_difference = (
                current_temperature - average_temperature
            )

            metrics["historical_average_temperature"] = round(
                average_temperature, 2
            )

            metrics["temperature_difference"] = round(
                temperature_difference, 2
            )

        if historical_thermal_rises and current_thermal_rise is not None:
            average_thermal_rise = (
                sum(historical_thermal_rises)
                / len(historical_thermal_rises)
            )

            thermal_rise_difference = (
                current_thermal_rise - average_thermal_rise
            )

            metrics["historical_average_thermal_rise"] = round(
                average_thermal_rise, 2
            )

            metrics["thermal_rise_difference"] = round(
                thermal_rise_difference, 2
            )

        return {
            "status": "comparison_available",
            "window_size": len(recent_records),
            "metrics": metrics
        }