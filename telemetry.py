class Telemetry:
    def __init__(self, normalized_data):
        self.data = normalized_data

    def snapshot(self, time_step):

        return {
            "identity": {
                "robot_id": self.data["robot_id"],
                "manufacturer": self.data["manufacturer"],
                "robot_type": self.data["robot_type"]
            },

            "telemetry": {

                "time_step": time_step,

                "motor_temperature":
                    self.data["motor_temperature"],

                "battery_level":
                    self.data["battery_level"],

                "battery_voltage":
                    self.data["battery_voltage"],

                "battery_current":
                    self.data["battery_current"],

                "battery_temperature":
                    self.data["battery_temperature"],

                "power_consumption":
                    self.data["power_consumption"],

                "voltage_drop":
                    self.data["voltage_drop"],

                "workload":
                    self.data["workload"],

                "robot_state":
                    self.data["robot_state"],

                "ambient_temperature":
                    self.data["ambient_temperature"]
            }
        }