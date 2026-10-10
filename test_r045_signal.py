from reliability_signal import ReliabilitySignal


signal_engine = ReliabilitySignal()


battery_levels = {
    60: 16.11,
    61: 14.55,
    62: 12.98,
    63: 11.40,
    64: 9.81,
    65: 8.22,
    66: 6.62,
    67: 5.00,
    68: 3.38,
    69: 1.76,
    70: 0.12,
    71: 0.00,
    72: 0.00,
    73: 0.00,
    74: 0.00,
    75: 0.00,
    76: 0.00,
    77: 0.00,
    78: 0.00,
    79: 0.00,
}


for time_step, battery_level in battery_levels.items():

    record = {
        "robot_id": "R045",
        "battery_level": battery_level,
        "motor_temperature": 28.0,
        "thermal_rise": 6.0,
        "voltage_drop": 0.0,
        "battery_current": 23.0
    }

    result = signal_engine.analyze(record)

    if result["signals"]:

        print(
            f"t={time_step} | "
            f"battery={battery_level:.2f} | "
            f"severity={result['severity']}"
        )

        for signal in result["signals"]:

            print(
                f"    → {signal['signal']}"
            )