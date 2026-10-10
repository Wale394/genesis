"""Robustness checks for realistic partial and imperfect field telemetry."""

import unittest

from genesis import Genesis
from ros2_telemetry_adapter import ROS2TelemetryAdapter


ROBOT = {
    "robot_id": "FIELD-R-ROBUST",
    "manufacturer": "ABB",
    "robot_type": "AMR",
}


def record(step, **telemetry):
    return {**ROBOT, "time_step": step, **telemetry}


def field_status(**values):
    """A ROS DiagnosticStatus-like mapping with explicit unit KeyValues."""
    units = {
        "motor_temperature": "C", "ambient_temperature": "C",
        "battery_temperature": "C", "battery_voltage": "V",
        "battery_current": "A", "battery_level": "%", "workload": "%",
    }
    kv = []
    for key, value in values.items():
        kv.append({"key": key, "value": value})
        if key in units:
            kv.append({"key": f"{key}_unit", "value": units[key]})
    return {"name": "robot/diagnostics", "values": kv}


def through_adapter(step, **values):
    adapter = ROS2TelemetryAdapter(**ROBOT)
    return adapter.adapt({
        "timestamp": step,
        "status": [field_status(**values)],
    })


def make_records(temperatures, *, timesteps=None, extras=None):
    timesteps = timesteps or list(range(1, len(temperatures) + 1))
    result = []
    for index, (step, temperature) in enumerate(zip(timesteps, temperatures)):
        fields = {"ambient_temperature": 22.0, "workload": 40.0}
        if temperature is not None:
            fields["motor_temperature"] = temperature
        if extras:
            fields.update(extras(index, step, temperature) or {})
        result.append(record(step, **fields))
    return result


def pattern_names(result):
    return {item["supporting_data"]["pattern"]
            for item in result["evidence_synthesis"]["pattern_evidence"]}


def pattern_evidence(result):
    return result["evidence_synthesis"]["pattern_evidence"]


def capability(result, name):
    return next(item for item in result["capability_discovery"]["analysis_capabilities"]
                if item["capability"] == name)


class GenesisFieldRobustnessTests(unittest.TestCase):
    def test_missing_observation_is_not_fabricated_and_gap_is_visible(self):
        result = Genesis().investigate(make_records([42, 43, None, 46, 47, 48]))
        coverage = result["capability_discovery"]["data_quality"]["field_coverage"]
        self.assertEqual(coverage["motor_temperature"]["missing_count"], 1)
        self.assertNotIn("motor_temperature", {
            item.get("field") for item in result["observations"]
            if item.get("value") is None
        })
        pattern_measurements = [
            observation
            for item in pattern_evidence(result)
            for observation in item["supporting_data"].get("observations", [])
        ]
        missing_sample = next(item for item in pattern_measurements if item.get("time_step") == 3)
        self.assertNotIn("motor_temperature", missing_sample)
        changes = [change
                   for item in pattern_evidence(result)
                   for change in item["supporting_data"].get("metrics", {}).get("changes", [])]
        self.assertFalse(any(change["from_time_step"] == 2 and change["to_time_step"] == 4
                             for change in changes))
        self.assertEqual(capability(result, "THERMAL_ANALYSIS")["status"], "AVAILABLE")

    def test_partial_battery_reports_unsupported_inputs_without_imputation(self):
        rows = [record(i, battery_voltage=48.0 - 0.05 * i,
                       battery_level=90.0 - i) for i in range(1, 7)]
        result = Genesis().investigate(rows)
        battery = capability(result, "BATTERY_ANALYSIS")
        self.assertEqual(battery["status"], "DEGRADED")
        self.assertEqual(battery["missing_data"], ["battery_current"])
        self.assertEqual(capability(result, "BATTERY_TEMPERATURE_ANALYSIS")["status"], "UNAVAILABLE")
        self.assertNotIn("battery_current", result["capability_discovery"]["available_telemetry"])
        self.assertNotIn("battery_temperature", result["capability_discovery"]["available_telemetry"])

    def test_nonfinite_diagnostic_is_omitted_with_adapter_limitation(self):
        adapted = through_adapter(1, motor_temperature=float("inf"), ambient_temperature="22")
        self.assertNotIn("motor_temperature", adapted["telemetry"])
        self.assertTrue(any("non-finite" in message for message in adapted["limitations"]))
        result = Genesis().investigate(adapted)
        quality = result["capability_discovery"]["data_quality"]
        self.assertIn("motor_temperature", result["capability_discovery"]["missing_telemetry"])
        self.assertTrue(quality["source_limitations"])

    def test_timestamp_gap_is_retained_in_pattern_support(self):
        result = Genesis().investigate(make_records(
            [42, 43, 44, 50, 51, 52], timesteps=[1, 2, 3, 7, 8, 9]
        ))
        changes = [change for pattern in pattern_evidence(result)
                   for change in pattern["supporting_data"].get("metrics", {}).get("changes", [])]
        gap_change = next(change for change in changes
                          if change["from_time_step"] == 3 and change["to_time_step"] == 7)
        self.assertEqual(gap_change["delta"], 6.0)
        pattern_items = result["evidence_synthesis"]["pattern_evidence"]
        self.assertTrue(all(item["source"] == "telemetry_pattern_engine" for item in pattern_items))
        self.assertEqual(result["evidence_synthesis"]["pattern_analysis"]["observations_analyzed"], 6)

    def test_noisy_thermal_sequence_is_described_without_diagnosis_or_cause(self):
        result = Genesis().investigate(make_records([50, 51, 49, 52, 50, 53, 51, 54, 52, 55]))
        self.assertTrue(pattern_names(result))
        self.assertIsNone(result["ml_inference"].get("diagnosis"))
        self.assertFalse(any("cause" in item["statement"].lower()
                             for item in result["evidence_synthesis"]["pattern_evidence"]))
        self.assertFalse(result["ml_inference"]["prediction_available"])

    def test_valid_missing_invalid_then_valid_preserves_limitation_not_recovery_claim(self):
        sequence = [
            through_adapter(1, motor_temperature="50", ambient_temperature="22"),
            through_adapter(2, motor_temperature="51", ambient_temperature="22"),
            through_adapter(3, motor_temperature="bad", ambient_temperature="22"),
            through_adapter(4, motor_temperature="53", ambient_temperature="22"),
        ]
        result = Genesis().investigate(sequence)
        quality = result["capability_discovery"]["data_quality"]
        self.assertEqual(quality["field_coverage"]["motor_temperature"]["missing_count"], 1)
        self.assertTrue(any("malformed numeric" in message
                            for message in quality["source_limitations"]))
        self.assertEqual(result["observations"][0]["value"], 53.0)
        self.assertEqual(result["outcome"]["status"], "OUTCOME_PENDING")
        self.assertNotIn("recovered", " ".join(result["limitations"]).lower())

    def test_sparse_history_is_insufficient_for_patterns_but_keeps_observations(self):
        result = Genesis().investigate(make_records([44, 45, 46]))
        self.assertEqual(result["evidence_synthesis"]["pattern_analysis"]["status"], "insufficient_data")
        self.assertFalse(pattern_evidence(result))
        self.assertEqual(capability(result, "TEMPORAL_PATTERN_ANALYSIS")["status"], "INSUFFICIENT")
        self.assertTrue(result["observations"])

    def test_constant_healthy_telemetry_does_not_create_a_pattern(self):
        result = Genesis().investigate(make_records([42.0] * 10))
        self.assertFalse(pattern_evidence(result))
        self.assertEqual(result["observations"][0]["value"], 42.0)

    def test_unknown_fields_are_preserved_as_unrecognized_not_capabilities(self):
        rows = [record(i, motor_temperature=40 + i, wheel_temperature=32 + i,
                       imu_acceleration=0.1, custom_motor_metric=7.0)
                for i in range(1, 7)]
        result = Genesis().investigate(rows)
        self.assertEqual(result["capability_discovery"]["data_quality"]["unrecognized_fields"],
                         ["custom_motor_metric", "imu_acceleration", "wheel_temperature"])
        names = {item["capability"] for item in result["capability_discovery"]["analysis_capabilities"]}
        self.assertFalse({"WHEEL_TEMPERATURE_ANALYSIS", "IMU_ACCELERATION_ANALYSIS",
                          "CUSTOM_MOTOR_METRIC_ANALYSIS"} & names)

    def test_realistic_partial_robot_capability_inventory_is_accurate(self):
        rows = [record(i, motor_temperature=40 + i, battery_voltage=48 - 0.03 * i,
                       battery_current=4.0, workload=30 + i)
                for i in range(1, 7)]
        result = Genesis().investigate(rows)
        self.assertEqual(capability(result, "THERMAL_ANALYSIS")["status"], "AVAILABLE")
        self.assertEqual(capability(result, "BATTERY_ANALYSIS")["status"], "AVAILABLE")
        self.assertEqual(capability(result, "BATTERY_TEMPERATURE_ANALYSIS")["status"], "UNAVAILABLE")
        self.assertEqual(capability(result, "TEMPORAL_PATTERN_ANALYSIS")["status"], "AVAILABLE")
        self.assertIn("workload", result["capability_discovery"]["available_telemetry"])
        self.assertNotIn("joint_temperature", result["capability_discovery"]["available_telemetry"])

    def test_evidence_categories_stay_separate_and_unavailable_ml_is_not_inferred(self):
        rows = make_records([42, 44, 46, 49, 56, 62], extras=lambda i, _s, _t: {
            "battery_voltage": 48.0, "battery_current": 4.0,
            "battery_level": 75.0, "workload": 40.0,
        })
        result = Genesis().investigate(rows)
        synthesis = result["evidence_synthesis"]
        types = {item["evidence_type"] for key in (
            "observations", "pattern_evidence", "engineering_evidence", "ml_evidence"
        ) for item in synthesis[key]}
        self.assertIn("OBSERVATION", types)
        self.assertIn("PATTERN", types)
        self.assertIn("ENGINEERING_SIGNAL", types)
        self.assertIn("ML_INFERENCE", types)
        self.assertTrue(any(item["availability"] == "UNAVAILABLE"
                            for item in synthesis["ml_evidence"]))
        self.assertFalse(result["ml_inference"]["prediction_available"])

    def test_patterns_do_not_generate_diagnosis_or_causal_claim(self):
        result = Genesis().investigate(make_records([42, 44, 46, 49, 53, 58]))
        for item in pattern_evidence(result):
            self.assertIn(item["category"], {"thermal", "thermal_workload"})
            self.assertIn("does not establish diagnosis or cause", item["limitations"][0])
        self.assertIsNone(result["ml_inference"].get("diagnosis"))
        self.assertFalse(any("cause" in item["statement"].lower()
                             for item in pattern_evidence(result)))

    def test_failure_metadata_does_not_trigger_observable_patterns(self):
        telemetry = make_records([42.0] * 6)
        labeled = [dict(item, failure_event=(index == 5), failure_type="thermal", label=1)
                   for index, item in enumerate(telemetry)]
        plain_result = Genesis().investigate(telemetry)
        labeled_result = Genesis().investigate(labeled)
        self.assertEqual(pattern_evidence(plain_result), pattern_evidence(labeled_result))
        self.assertFalse(pattern_evidence(labeled_result))


if __name__ == "__main__":
    unittest.main()
