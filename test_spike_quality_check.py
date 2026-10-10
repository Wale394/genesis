
from genesis_system.core.observation_quality import ObservationQuality


def assess_spike():
    engine = ObservationQuality()

    # Five stable previous readings, followed by the observed spike.
    history = [
        {"motor_temperature": 43.0} for _ in range(5)
    ]
    current = {"motor_temperature": 255.0}

    result = engine.assess(current, history)

    thermal = result["groups"]["thermal"]

    print("Overall quality:", result["status"])
    print("Thermal quality:", thermal["status"])
    print("Thermal issues:", thermal["issues"])

    abrupt_change = any(
        issue.get("check") == "abrupt_change"
        and "motor_temperature" in issue.get("fields", [])
        for issue in thermal["issues"]
    )

    print(
        "Abrupt temperature change flagged:",
        abrupt_change,
    )


if __name__ == "__main__":
    assess_spike()
