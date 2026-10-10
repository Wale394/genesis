
from unittest import result

from genesis_system.core.telemetry_pattern_engine import TelemetryPatternEngine


def run_test(name, temperatures, expected_pattern):
    engine = TelemetryPatternEngine()

    records = [
        {
            "time_step": index + 1,
            "motor_temperature": temperature,
        }
        for index, temperature in enumerate(temperatures)
    ]

    result = engine.analyze(records)
    detected = [
        pattern.get("pattern")
        for pattern in result.get("patterns", [])
    ]

    print(f"\n{name}")
    print("Status:", result.get("status"))
    print("Raw pattern records:", result.get("patterns", []))
    print("Full result:", result)

    if expected_pattern is None:
        passed = not detected
    else:
        passed = any(
            expected_pattern in str(pattern)
            for pattern in detected
        )

    print("PASS" if passed else "CHECK")
    return passed


if __name__ == "__main__":
    rising = [40, 41, 42, 43, 44, 45, 46, 47, 48, 49]
    flat = [40] * 10

    results = [
        run_test("Sustained-rise test", rising, "SUSTAINED_RISE"),
        run_test("Flat-temperature control", flat, None),
    ]

    print(f"\nSummary: {sum(results)}/{len(results)} checks passed")
