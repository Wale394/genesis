import copy
import unittest

from telemetry_pattern_engine import TelemetryPatternEngine


def records_for(**series):
    count = max(len(values) for values in series.values())
    return [
        {"time_step": index, **{name: values[index] for name, values in series.items()}}
        for index in range(count)
    ]


def names(result):
    return {pattern["pattern"] for pattern in result["patterns"]}


class TelemetryPatternEngineTests(unittest.TestCase):
    def test_sustained_rising_sequence(self):
        result = TelemetryPatternEngine().analyze(records_for(
            motor_temperature=[40, 40.8, 41.6, 42.4, 43.2, 44.0]
        ))
        self.assertIn("SUSTAINED_RISE", names(result))
        pattern = next(p for p in result["patterns"] if p["pattern"] == "SUSTAINED_RISE")
        self.assertEqual(pattern["metrics"]["net_increase"], 4.0)
        self.assertEqual(len(pattern["observations"]), 6)

    def test_volatile_rising_sequence(self):
        values = [67.33, 65.98, 66.51, 68.83, 64.81, 64.26, 67.28, 67.26, 77.61, 68.09]
        result = TelemetryPatternEngine().analyze(records_for(motor_temperature=values))
        self.assertIn("VOLATILE_RISE", names(result))

    def test_rapid_spike_reports_observed_delta(self):
        result = TelemetryPatternEngine().analyze(records_for(
            motor_temperature=[40, 40.5, 41, 41.5, 42, 50]
        ))
        pattern = next(p for p in result["patterns"] if p["pattern"] == "RAPID_SPIKE")
        self.assertEqual(pattern["metrics"]["observed_delta"], 8.0)
        self.assertIn("8.00", pattern["description"])

    def test_persistent_elevation(self):
        result = TelemetryPatternEngine().analyze(records_for(
            motor_temperature=[40, 41, 40, 42, 43.5, 44, 45, 46, 46, 46]
        ))
        self.assertIn("PERSISTENT_ELEVATION", names(result))

    def test_repeated_spikes_separated_by_declines(self):
        result = TelemetryPatternEngine().analyze(records_for(
            motor_temperature=[40, 40, 46, 43, 43, 49, 47, 47]
        ))
        pattern = next(p for p in result["patterns"] if p["pattern"] == "REPEATED_SPIKES")
        self.assertEqual(pattern["metrics"]["spike_deltas"], [6.0, 6.0])
        self.assertTrue(pattern["metrics"]["intervening_declines_observed"])

    def test_declining_battery(self):
        result = TelemetryPatternEngine().analyze(records_for(
            battery_level=[80, 79, 78, 77, 76, 75, 74, 73, 72, 71]
        ))
        pattern = next(p for p in result["patterns"] if p["pattern"] == "DECLINING_BATTERY")
        self.assertEqual(pattern["metrics"]["measurement"], "battery_level")
        self.assertEqual(pattern["metrics"]["net_decline"], 9.0)

    def test_voltage_instability(self):
        result = TelemetryPatternEngine().analyze(records_for(
            battery_voltage=[48.0, 48.3, 48.0, 48.4, 48.1, 48.3, 48.0]
        ))
        self.assertIn("VOLTAGE_INSTABILITY", names(result))

    def test_thermal_with_high_workload_is_observation_only(self):
        result = TelemetryPatternEngine().analyze(records_for(
            motor_temperature=[40, 41, 42, 45, 46, 47, 48],
            workload=[10, 20, 20, 80, 90, 85, 95],
        ))
        pattern = next(p for p in result["patterns"] if p["pattern"] == "THERMAL_WITH_HIGH_WORKLOAD")
        self.assertEqual(pattern["metrics"]["coobservation_count"], 2)
        self.assertIn("association only", pattern["description"])
        self.assertNotIn("cause", pattern)
        self.assertNotIn("recommendation", pattern)
        self.assertNotIn("probability", pattern)

    def test_insufficient_history(self):
        result = TelemetryPatternEngine().analyze(records_for(motor_temperature=[40, 41, 42, 43]))
        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["patterns"], [])

    def test_constant_healthy_telemetry_has_no_patterns(self):
        result = TelemetryPatternEngine().analyze(records_for(
            motor_temperature=[40] * 10,
            ambient_temperature=[25] * 10,
            battery_level=[80] * 10,
            battery_voltage=[48] * 10,
            workload=[20] * 10,
        ))
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["patterns"], [])

    def test_missing_optional_fields_are_supported(self):
        result = TelemetryPatternEngine().analyze(records_for(
            motor_temperature=[40, 41, 42, 43, 44]
        ))
        self.assertEqual(result["status"], "available")
        self.assertIn("SUSTAINED_RISE", names(result))
        self.assertTrue(any("Workload telemetry is unavailable" in item for item in result["limitations"]))

    def test_precomputed_thermal_rise_feature_records_are_supported(self):
        result = TelemetryPatternEngine().analyze(records_for(
            thermal_rise=[10, 10.8, 11.6, 12.4, 13.2, 14.0]
        ))
        pattern = next(p for p in result["patterns"] if p["pattern"] == "SUSTAINED_RISE")
        self.assertEqual(pattern["metrics"]["measurement"], "thermal_rise")

    def test_repeated_execution_is_deterministic_and_json_compatible(self):
        records = records_for(
            motor_temperature=[40, 40, 46, 43, 43, 49, 47, 47],
            workload=[20, 20, 30, 30, 40, 80, 90, 90],
        )
        engine = TelemetryPatternEngine()
        first = engine.analyze(records)
        second = engine.analyze(records)
        self.assertEqual(first, second)
        import json
        json.dumps(first)

    def test_failure_metadata_and_labels_do_not_trigger_patterns(self):
        records = records_for(motor_temperature=[40] * 10)
        control = TelemetryPatternEngine().analyze(records)
        poisoned = copy.deepcopy(records)
        for row in poisoned:
            row.update({
                "failure_event": True,
                "failure_type": "thermal",
                "label": 1,
                "failure_type_label": "thermal",
                "degradation_level": 1.0,
            })
        with_metadata = TelemetryPatternEngine().analyze(poisoned)
        self.assertEqual(control, with_metadata)
        self.assertEqual(with_metadata["patterns"], [])

    def test_regression_trajectories_have_distinct_structure(self):
        r032 = [72.75, 73.64, 74.85, 76.67, 76.70, 76.64, 76.68, 77.90, 79.48, 79.41]
        r077 = [67.33, 65.98, 66.51, 68.83, 64.81, 64.26, 67.28, 67.26, 77.61, 68.09]
        engine = TelemetryPatternEngine()
        r032_patterns = names(engine.analyze(records_for(motor_temperature=r032)))
        r077_patterns = names(engine.analyze(records_for(motor_temperature=r077)))
        self.assertIn("SUSTAINED_RISE", r032_patterns)
        self.assertNotIn("VOLATILE_RISE", r032_patterns)
        self.assertIn("VOLATILE_RISE", r077_patterns)
        self.assertNotIn("SUSTAINED_RISE", r077_patterns)
        self.assertIn("RAPID_SPIKE", r077_patterns)

