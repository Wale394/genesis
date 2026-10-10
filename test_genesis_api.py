import json
import unittest

from demo_genesis_investigation import (
    ENGINEERING_SIGNAL,
    demo_historical_incidents,
    demo_peer_records,
    demo_telemetry_records,
)
from genesis import Genesis


def configured_genesis():
    return Genesis(
        peer_records=demo_peer_records(),
        historical_incidents=demo_historical_incidents(),
    )


class GenesisApiTests(unittest.TestCase):
    def test_01_genesis_can_be_instantiated(self):
        self.assertIsInstance(Genesis(), Genesis)

    def test_02_single_normalized_record_is_accepted(self):
        result = Genesis().investigate(demo_telemetry_records(count=1)[0])
        self.assertEqual(result["processing"]["observation_count"], 1)
        self.assertEqual(result["observation_quality"]["prediction_ready"], False)

    def test_03_multiple_chronological_records_are_accepted(self):
        result = configured_genesis().investigate(demo_telemetry_records(count=6))
        self.assertEqual(result["processing"]["observation_count"], 6)
        self.assertEqual(result["reliability_state"]["current"], "CRITICAL")

    def test_04_result_is_json_compatible(self):
        result = configured_genesis().investigate(demo_telemetry_records(count=6))
        decoded = json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False))
        self.assertIn("evidence_synthesis", decoded)

    def test_05_robot_identity_is_preserved(self):
        result = configured_genesis().investigate(demo_telemetry_records(count=6))
        self.assertEqual(result["robot"], {
            "robot_id": "R004", "manufacturer": "ABB", "robot_type": "AMR",
        })

    def test_06_observation_quality_is_preserved(self):
        result = configured_genesis().investigate(demo_telemetry_records(count=6))
        self.assertEqual(result["observation_quality"]["status"], "AVAILABLE")
        self.assertEqual(result["observation_quality"]["groups"]["thermal"]["status"], "AVAILABLE")

    def test_07_engineering_signals_are_preserved(self):
        result = configured_genesis().investigate(demo_telemetry_records(count=6))
        signals = {item["signal"] for item in result["engineering_signals"]["signals"]}
        self.assertIn(ENGINEERING_SIGNAL, signals)

    def test_08_fleet_context_is_preserved(self):
        result = configured_genesis().investigate(demo_telemetry_records(count=6))
        motor = result["fleet_context"]["metrics"]["motor_temperature"]
        self.assertEqual(result["fleet_context"]["comparable_robot_count"], 3)
        self.assertEqual(motor["peer_mean"], 43.0)

    def test_09_historical_memory_is_preserved(self):
        result = configured_genesis().investigate(demo_telemetry_records(count=6))
        self.assertEqual(result["historical_memory"]["match_count"], 2)

    def test_10_ml_remains_unavailable_without_a_model(self):
        result = Genesis().investigate(demo_telemetry_records(count=6))
        self.assertFalse(result["ml_inference"]["prediction_available"])

    def test_11_no_probability_is_fabricated(self):
        result = Genesis().investigate(demo_telemetry_records(count=6))
        self.assertIsNone(result["ml_inference"]["probability"])

    def test_12_recommendation_is_preserved(self):
        result = Genesis().investigate(demo_telemetry_records(count=6))
        self.assertTrue(result["recommendation"]["recommendation"])

    def test_13_human_action_is_pending_for_new_investigation(self):
        result = Genesis().investigate(demo_telemetry_records(count=6))
        self.assertEqual(result["human_action"]["status"], "PENDING")

    def test_14_outcome_is_pending_for_new_investigation(self):
        result = Genesis().investigate(demo_telemetry_records(count=6))
        self.assertEqual(result["outcome"]["status"], "OUTCOME_PENDING")

    def test_15_limitations_are_preserved(self):
        result = Genesis().investigate(demo_telemetry_records(count=6))
        self.assertTrue(result["limitations"])
        self.assertTrue(any("model artifact" in item for item in result["limitations"]))

    def test_16_existing_reliability_state_is_preserved(self):
        result = Genesis().investigate(demo_telemetry_records(count=6))
        self.assertEqual(result["reliability_state"]["current"], "CRITICAL")

    def test_17_malformed_input_raises_clear_error(self):
        with self.assertRaisesRegex(ValueError, "robot_id.*required"):
            Genesis().investigate({"motor_temperature": 40.0})

    def test_18_raw_normalizable_record_uses_existing_normalizer(self):
        record = {
            "id": "RAW-1", "manufacturer": "ABB", "robotType": "AMR",
            "motorTemperature": 104.0, "temperatureUnit": "F",
            "ambientTemperature": 68.0, "ambientTemperatureUnit": "F",
            "batteryPercentage": 80.0, "batteryVoltage": 48.0,
            "batteryCurrent": 12.0, "batteryTemperature": 30.0,
            "powerConsumption": 800.0, "voltageDrop": 0.5,
            "workload": 35.0, "status": "active", "time_step": 1,
        }
        result = Genesis().investigate(record)
        observed = next(
            item["value"] for item in result["observations"]
            if item.get("field") == "motor_temperature"
        )
        self.assertEqual(observed, 40.0)

    def test_19_out_of_order_records_raise_clear_error(self):
        records = demo_telemetry_records(count=2)
        with self.assertRaisesRegex(ValueError, "not later than the previous observation"):
            Genesis().investigate(list(reversed(records)))

    def test_20_temporal_features_are_processed_in_batch_order(self):
        result = Genesis().investigate(demo_telemetry_records(count=6))
        changes = {
            item["field"]: item["value"]
            for item in result["temporal_evidence"]
        }
        self.assertEqual(changes["temperature_change"], 3.0)

    def test_21_single_record_can_continue_on_same_facade(self):
        genesis = Genesis()
        records = demo_telemetry_records(count=2)
        genesis.investigate(records[0])
        result = genesis.investigate(records[1])
        self.assertEqual(result["processing"]["observation_count"], 1)
        self.assertEqual(result["processing"]["telemetry"][0]["motor_temperature"], 44.0)


if __name__ == "__main__":
    unittest.main()
