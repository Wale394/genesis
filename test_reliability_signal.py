from reliability_signal import ReliabilitySignal


signal_engine = ReliabilitySignal()


test_records = [

    {
        "robot_id": "TEST-BATTERY",
        "battery_level": 3.38,
        "motor_temperature": 28.84,
        "thermal_rise": 6.15,
        "voltage_drop": 0.0,
        "battery_current": 22.85
    },

    {
        "robot_id": "TEST-THERMAL",
        "battery_level": 80.0,
        "motor_temperature": 65.0,
        "thermal_rise": 40.0,
        "voltage_drop": 0.0,
        "battery_current": 20.0
    },

    {
        "robot_id": "TEST-NORMAL",
        "battery_level": 80.0,
        "motor_temperature": 35.0,
        "thermal_rise": 10.0,
        "voltage_drop": 1.0,
        "battery_current": 20.0
    }
]


for record in test_records:

    result = signal_engine.analyze(
        record
    )

    print("\n--------------------------------")
    print(
        f"Robot: {record['robot_id']}"
    )

    print(
        f"Status: {result['status']}"
    )

    print(
        f"Severity: {result['severity']}"
    )

    for signal in result["signals"]:

        print(
            f"Signal: {signal['signal']}"
        )

        print(
            f"Message: {signal['message']}"
        )