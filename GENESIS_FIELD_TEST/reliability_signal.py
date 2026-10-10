class ReliabilitySignal:

    def __init__(
        self,
        critical_battery_level=5.0,
        rapid_battery_drop=5.0,
        critical_motor_temperature=60.0,
        critical_thermal_rise=35.0,
        critical_voltage_drop=10.0,
        critical_battery_current=40.0
    ):
        self.critical_battery_level = critical_battery_level
        self.rapid_battery_drop = rapid_battery_drop

        self.critical_motor_temperature = (
            critical_motor_temperature
        )

        self.critical_thermal_rise = (
            critical_thermal_rise
        )

        self.critical_voltage_drop = (
            critical_voltage_drop
        )

        self.critical_battery_current = (
            critical_battery_current
        )

    # ========================================================
    # BATTERY
    # ========================================================

    def check_battery_level(self, record):

        battery_level = record.get(
            "battery_level"
        )

        if battery_level is None:
            return None

        if battery_level <= self.critical_battery_level:

            return {
                "signal": "critical_battery_level",
                "severity": "critical",
                "value": battery_level,
                "message": (
                    "Battery level is critically low."
                )
            }

        return None

    def check_battery_drop(self, record):

        battery_change = record.get(
            "battery_change"
        )

        if battery_change is None:
            return None

        if battery_change <= -self.rapid_battery_drop:

            return {
                "signal": "rapid_battery_depletion",
                "severity": "warning",
                "value": battery_change,
                "message": (
                    "Battery level is decreasing rapidly."
                )
            }

        return None

    # ========================================================
    # THERMAL
    # ========================================================

    def check_motor_temperature(self, record):

        temperature = record.get(
            "motor_temperature"
        )

        if temperature is None:
            return None

        if temperature >= self.critical_motor_temperature:

            return {
                "signal": "critical_motor_temperature",
                "severity": "critical",
                "value": temperature,
                "message": (
                    "Motor temperature is critically high."
                )
            }

        return None

    def check_thermal_rise(self, record):

        thermal_rise = record.get(
            "thermal_rise"
        )

        if thermal_rise is None:
            return None

        if thermal_rise >= self.critical_thermal_rise:

            return {
                "signal": "critical_thermal_rise",
                "severity": "critical",
                "value": thermal_rise,
                "message": (
                    "Thermal rise is critically high."
                )
            }

        return None

    # ========================================================
    # POWER
    # ========================================================

    def check_voltage_drop(self, record):

        voltage_drop = record.get(
            "voltage_drop"
        )

        if voltage_drop is None:
            return None

        if voltage_drop >= self.critical_voltage_drop:

            return {
                "signal": "critical_voltage_drop",
                "severity": "critical",
                "value": voltage_drop,
                "message": (
                    "Voltage drop is critically high."
                )
            }

        return None

    def check_battery_current(self, record):

        current = record.get(
            "battery_current"
        )

        if current is None:
            return None

        if current >= self.critical_battery_current:

            return {
                "signal": "critical_battery_current",
                "severity": "warning",
                "value": current,
                "message": (
                    "Battery current is unusually high."
                )
            }

        return None

    # ========================================================
    # COMPLETE SIGNAL ANALYSIS
    # ========================================================

    def analyze(self, record):

        signals = []

        checks = [
            self.check_battery_level,
            self.check_battery_drop,
            self.check_motor_temperature,
            self.check_thermal_rise,
            self.check_voltage_drop,
            self.check_battery_current
        ]

        for check in checks:

            result = check(record)

            if result is not None:
                signals.append(result)

        if not signals:

            return {
                "status": "normal",
                "severity": "normal",
                "signals": []
            }

        severity_order = {
            "normal": 0,
            "warning": 1,
            "critical": 2
        }

        highest_severity = max(
            signals,
            key=lambda signal:
            severity_order[signal["severity"]]
        )["severity"]

        return {
            "status": "signal_detected",
            "severity": highest_severity,
            "signals": signals
        }