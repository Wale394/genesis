class Normalizer:

    def __init__(self, field_mappings=None, state_mappings=None):

        if field_mappings is None:
            self.field_mappings = {
                "robot_id": ["id", "robot_id"],
                "motor_temperature": ["motorTemperature", "motor_temp"],
                "temperature_unit": ["temperatureUnit", "temp_unit"],
                "battery_level": ["batteryPercentage", "battery"],
                "robot_state": ["status", "state"],
                "ambient_temperature": ["ambientTemperature", "ambient_temp"],
                "ambient_temperature_unit": [
                    "ambientTemperatureUnit",
                    "ambient_temp_unit"
                ],
                "battery_voltage": ["batteryVoltage", "battery_voltage"],
                "battery_current": ["batteryCurrent", "battery_current"],
                "battery_temperature": [
                    "batteryTemperature",
                    "battery_temperature"
                ],
                "power_consumption": [
                    "powerConsumption",
                    "power_consumption"
                ],
                "voltage_drop": [
                    "voltageDrop",
                    "voltage_drop"
                ],
                "workload": ["workload", "load"],
                "manufacturer": ["manufacturer", "brand"],
                "robot_type": ["robotType", "robot_type"]

            }
        else:
            self.field_mappings = field_mappings

        if state_mappings is None:
            self.state_mappings = {
                "active": "working",
                "running": "working",
                "operating": "working",
                "idle": "idle",
                "standby": "idle"
            }
        else:
            self.state_mappings = state_mappings

    def get_field(self, raw_data, field_name):

        for key in self.field_mappings[field_name]:
            if key in raw_data:
                return raw_data[key]

        raise KeyError(
            f"None of the expected keys for '{field_name}' "
            f"were found in the raw data."
        )

    def fahrenheit_to_celsius(self, fahrenheit):
        return (fahrenheit - 32) * 5.0 / 9.0

    def normalize_temperature(self, temperature, unit):

        if unit == "F":
            return self.fahrenheit_to_celsius(temperature)

        elif unit == "C":
            return temperature

        elif unit == "K":
            return temperature - 273.15

        else:
            raise ValueError(
                "Unit must be 'F' for Fahrenheit, "
                "'C' for Celsius, or 'K' for Kelvin."
            )

    def normalize(self, raw_data):

        normalized_temperature = self.normalize_temperature(
            self.get_field(raw_data, "motor_temperature"),
            self.get_field(raw_data, "temperature_unit")
        )

        normalized_ambient_temperature = self.normalize_temperature(
            self.get_field(raw_data, "ambient_temperature"),
            self.get_field(raw_data, "ambient_temperature_unit")
        )

        raw_state = self.get_field(raw_data, "robot_state")

        normalized_data = {
            "robot_id": self.get_field(raw_data, "robot_id"),

            "manufacturer": self.get_field(
                raw_data,
                "manufacturer"
            ),

            "robot_type": self.get_field(
                raw_data,
                "robot_type"
            ),

            "motor_temperature": normalized_temperature,

            "battery_level": self.get_field(
                raw_data,
                "battery_level"
            ),

            "battery_voltage": self.get_field(
                raw_data,
                "battery_voltage"
            ),

            "battery_current": self.get_field(
                raw_data,
                "battery_current"
            ),

            "battery_temperature": self.get_field(
                raw_data,
                "battery_temperature"
            ),

            "power_consumption": self.get_field(
                raw_data,
                "power_consumption"
            ),

            "voltage_drop": self.get_field(
                raw_data,
                "voltage_drop"
            ),

            "workload": self.get_field(
                raw_data,
                "workload"
            ),

            "robot_state": self.normalize_state(
                raw_state
            ),

            "ambient_temperature": normalized_ambient_temperature
        }

        return normalized_data

    def normalize_state(self, state):

        if state in self.state_mappings:
            return self.state_mappings[state]

        raise ValueError(
            f"State '{state}' is not recognized in the state mappings."
        )