import unittest

from baseline_engine import (
    BASELINE_ELIGIBLE,
    BASELINE_INELIGIBLE,
    BASELINE_UNKNOWN,
    BaselineEngine,
)
from genesis import Genesis


def external_record(step, temperature, rise, battery, **extra):
    return {
        "robot_id": "FIELD-R001",
        "time_step": step,
        "motor_temperature": temperature,
        "thermal_rise": rise,
        "battery_level": battery,
        **extra,
    }


class BaselineEligibilityTests(unittest.TestCase):
    def test_external_records_without_health_are_unknown_not_healthy(self):
        records = [
            external_record(step, 40 + step, 2 + step, 80 - step)
            for step in range(3)
        ]

        result = BaselineEngine(minimum_records=3).build_baseline(records)

        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["records_used"], 0)
        self.assertEqual(result["metrics"], {})

    def test_explicitly_approved_external_records_use_existing_aggregation(self):
        records = [
            external_record(
                step,
                40 + step,
                2 + step,
                80 - 10 * step,
                baseline_eligibility=BASELINE_ELIGIBLE,
            )
            for step in range(3)
        ]

        result = BaselineEngine(minimum_records=3).build_baseline(records)

        self.assertEqual(result["status"], "baseline_available")
        self.assertEqual(result["records_used"], 3)
        self.assertEqual(result["metrics"], {
            "average_motor_temperature": 41.0,
            "average_thermal_rise": 3.0,
            "average_battery_level": 70.0,
        })

    def test_explicitly_ineligible_records_are_excluded(self):
        records = [
            external_record(
                step, 90.0, 60.0, 1.0,
                baseline_eligibility=BASELINE_INELIGIBLE,
            )
            for step in range(3)
        ]

        result = BaselineEngine(minimum_records=3).build_baseline(records)

        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["records_used"], 0)

    def test_simulator_failure_records_remain_excluded(self):
        records = [
            external_record(
                0, 41.0, 3.0, 75.0,
                health="healthy", failure_event=False,
            ),
            external_record(
                1, 99.0, 70.0, 0.0,
                health="healthy", failure_event=True,
            ),
            external_record(
                2, 98.0, 69.0, 1.0,
                health="failed", failure_event=False,
            ),
        ]

        result = BaselineEngine(minimum_records=1).build_baseline(records)

        self.assertEqual(result["status"], "baseline_available")
        self.assertEqual(result["records_used"], 1)
        self.assertEqual(result["metrics"]["average_motor_temperature"], 41.0)

    def test_mixed_history_uses_only_explicitly_eligible_records(self):
        records = [
            external_record(0, 10.0, 1.0, 10.0, baseline_eligibility=BASELINE_ELIGIBLE),
            external_record(1, 90.0, 90.0, 1.0, baseline_eligibility=BASELINE_INELIGIBLE),
            external_record(2, 50.0, 50.0, 50.0, baseline_eligibility=BASELINE_UNKNOWN),
            external_record(3, 30.0, 3.0, 30.0, baseline_eligibility=BASELINE_ELIGIBLE),
            external_record(4, 100.0, 100.0, 0.0),  # unknown: no decision or health
        ]

        result = BaselineEngine(minimum_records=2).build_baseline(records)

        self.assertEqual(result["status"], "baseline_available")
        self.assertEqual(result["records_used"], 2)
        self.assertEqual(result["metrics"], {
            "average_motor_temperature": 20.0,
            "average_thermal_rise": 2.0,
            "average_battery_level": 20.0,
        })

    def test_degraded_explicit_record_is_not_eligible(self):
        record = external_record(
            0,
            40.0,
            5.0,
            80.0,
            baseline_eligibility=BASELINE_ELIGIBLE,
            observation_quality={"status": "DEGRADED", "groups": {}},
        )

        result = BaselineEngine(minimum_records=1).build_baseline([record])

        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["records_used"], 0)

    def test_genesis_preserves_explicit_decision_in_streaming_history(self):
        genesis = Genesis()
        records = [
            {
                "identity": {"robot_id": "FIELD-R001"},
                "telemetry": {
                    "time_step": step,
                    "motor_temperature": 40.0 + step,
                    "ambient_temperature": 20.0,
                    "battery_level": 80.0 - step,
                },
                "baseline_eligibility": BASELINE_ELIGIBLE,
            }
            for step in range(10)
        ]

        result = genesis.investigate(records)
        history = genesis._records_by_robot["FIELD-R001"]
        baseline = genesis._pipeline.baseline_engine.build_baseline(history)

        self.assertTrue(all(
            item["baseline_eligibility"] == BASELINE_ELIGIBLE
            for item in history
        ))
        self.assertEqual(baseline["records_used"], 10)
        self.assertEqual(baseline["metrics"]["average_motor_temperature"], 44.5)
        self.assertNotIn(
            "baseline_eligibility",
            result["capability_discovery"]["data_quality"]["unrecognized_fields"],
        )


if __name__ == "__main__":
    unittest.main()
