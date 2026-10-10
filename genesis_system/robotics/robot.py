class Robot:
    def __init__(self, robot_id, manufacturer, model,
                 firmware_version="1.0.0",
                 battery_level=100,
                 motor_temperature=25.0):

        self.robot_id = robot_id
        self.manufacturer = manufacturer
        self.model = model
        self.firmware_version = firmware_version
        self.battery_level = battery_level
        self.motor_temperature = motor_temperature

    def update_battery_level(self, new_battery_level):
        if 0 <= new_battery_level <= 100:
            self.battery_level = new_battery_level
        else:
            raise ValueError("Battery level must be between 0 and 100.")

    def update_motor_temperature(self, new_motor_temperature):
        if new_motor_temperature >= 0:
            self.motor_temperature = new_motor_temperature
        else:
            raise ValueError(
                "Motor temperature must be a non-negative value."
            )

    def update(self, temperature_change = 1):
        self.battery_level = self.battery_level - 1

        if self.battery_level < 0:
            self.battery_level = 0

        self.motor_temperature = self.motor_temperature + temperature_change