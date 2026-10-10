from reliability_fusion import ReliabilityFusion


fusion = ReliabilityFusion()


record = {
    "robot_id": "R045",
    "battery_level": 5.0,
    "motor_temperature": 28.0,
    "thermal_rise": 6.0,
    "voltage_drop": 0.0,
    "battery_current": 23.0
}


result = fusion.evaluate(
    feature_record=record,
    ml_probability=0.18,
    ml_prediction=0
)


print("\n================================")
print("GENESIS FUSION TEST")
print("================================")

print(
    "ML probability:",
    result["ml"]["probability"]
)

print(
    "ML prediction:",
    result["ml"]["prediction"]
)

print(
    "Engineering severity:",
    result["engineering"]["severity"]
)

print(
    "Engineering signals:"
)

for signal in result["engineering"]["signals"]:

    print(
        f"  → {signal['signal']}"
    )

print(
    "Final prediction:",
    result["final"]["prediction"]
)

print(
    "Final risk:",
    result["final"]["risk"]
)