from types import SimpleNamespace
import unittest

from data_availability import DataAvailability
from feature_contract import (
    DEPLOYABLE_FEATURES,
    HISTORY_COUNT_FIELD,
    SIMULATOR_ONLY_FIELDS,
    build_features,
)
from feature_engineering import FeatureEngineer
from prediction_engine import PredictionEngine
from telemetry_features import TelemetryFeatureBuilder
from train_model import ReliabilityModel


def telemetry_record(robot_id, step, battery=None, temperature=None):
    temperature = temperature if temperature is not None else 30.0 + step
    return {
        "robot_id": robot_id,
        "manufacturer": "Test Robotics",
        "robot_type": "AMR",
        "time_step": step,
        "motor_temperature": temperature,
        "ambient_temperature": 20.0,
        "battery_level": battery if battery is not None else 100.0 - step,
        "battery_voltage": 48.0 - step * 0.1,
        "battery_current": 10.0 + step,
        "battery_temperature": 25.0 + step * 0.2,
        "power_consumption": 400.0 + step * 10,
        "voltage_drop": step * 0.1,
        "workload": 25.0 + step,
        "robot_state": "working",
        "label": 0,
        "failure_type_label": "none",
        "failure_event": False,
        "recovery_event": False,
    }


def snapshot(record):
    identity = {
        key: record[key]
        for key in ("robot_id", "manufacturer", "robot_type")
    }
    telemetry = {
        key: value
        for key, value in record.items()
        if key not in identity and key not in {
            "label", "failure_type_label", "failure_event", "recovery_event"
        }
    }
    return {"identity": identity, "telemetry": telemetry}


def test_offline_and_streaming_features_match_for_same_sequence():
    records = [telemetry_record("A", step) for step in range(1, 8)]
    offline = FeatureEngineer().create_features(records)
    builder = TelemetryFeatureBuilder()
    streaming = [builder.build(snapshot(record)) for record in records]

    for offline_record, stream_record in zip(offline, streaming):
        for feature in DEPLOYABLE_FEATURES:
            assert offline_record[feature] == stream_record[feature]


def test_robot_histories_are_independent():
    a_records = [
        telemetry_record("A", step, temperature=80.0 + step)
        for step in range(1, 7)
    ]
    b_records = [
        telemetry_record("B", step, temperature=20.0 + step)
        for step in range(1, 7)
    ]

    interleaved_builder = TelemetryFeatureBuilder()
    interleaved = {}
    for a_record, b_record in zip(a_records, b_records):
        interleaved["A"] = interleaved_builder.build(snapshot(a_record))
        interleaved["B"] = interleaved_builder.build(snapshot(b_record))

    b_only_builder = TelemetryFeatureBuilder()
    b_only = [b_only_builder.build(snapshot(record)) for record in b_records]
    for feature in DEPLOYABLE_FEATURES:
        assert interleaved["B"][feature] == b_only[-1][feature]


def test_five_sample_windows_include_current_observation():
    history = []
    result = None
    for step, temperature in enumerate((10, 20, 30, 40, 50)):
        current = telemetry_record("A", step, temperature=temperature)
        result = build_features(current, history)
        history.append(current)

    assert result["temperature_avg_5"] == 30.0
    assert result["thermal_rise_max_5"] == 30.0
    assert result["thermal_rise_avg_5"] == 10.0


def test_battery_decline_and_rate_are_positive_for_declining_values():
    history = []
    result = None
    for step, battery in enumerate((100, 95, 90, 85)):
        current = telemetry_record("A", step, battery=battery)
        result = build_features(current, history)
        history.append(current)

    assert result["battery_decline_3"] == 10.0
    assert result["battery_drop_rate_3"] == 15.0
    assert result["battery_voltage_drop_rate_3"] > 0


def test_prediction_waits_for_four_prior_observations():
    builder = TelemetryFeatureBuilder()
    availability = DataAvailability()
    model = SimpleNamespace(feature_names_in_=list(DEPLOYABLE_FEATURES))

    for step in range(1, 5):
        result = builder.build(snapshot(telemetry_record("A", step)))
        status = availability.can_run_prediction(result, model)
        assert status["can_predict"] is False
        assert status["required_history"] == 4

    result = builder.build(snapshot(telemetry_record("A", 5)))
    status = availability.can_run_prediction(result, model)
    assert result[HISTORY_COUNT_FIELD] == 4
    assert status["history_ready"] is True
    assert status["can_predict"] is True


def test_risk_model_schema_contains_only_deployable_features():
    row = telemetry_record("A", 5)
    history = [telemetry_record("A", step) for step in range(1, 5)]
    row.update(build_features(row, history))
    row.update({
        "battery_health": 0.8,
        "battery_stress": 4.0,
        "degradation_level": 2.0,
        "health": "degrading",
        "initial_health": "healthy",
        "failure_event": False,
        "failure_type": "none",
        "recovery_event": False,
        "failure_type_label": "none",
        "label": 0,
        "horizon_valid": True,
    })

    features, _, _ = ReliabilityModel([row]).prepare_data()
    assert list(features.columns) == list(DEPLOYABLE_FEATURES)
    assert not set(features.columns).intersection(SIMULATOR_ONLY_FIELDS)


def test_prediction_input_uses_trained_order_and_drops_other_fields():
    row = telemetry_record("A", 5)
    history = [telemetry_record("A", step) for step in range(1, 5)]
    row.update(build_features(row, history))
    row["battery_stress"] = 99.0
    expected_order = list(reversed(DEPLOYABLE_FEATURES))
    model = SimpleNamespace(feature_names_in_=expected_order)

    prepared = PredictionEngine(model)._prepare_input([row])

    assert list(prepared.columns) == expected_order
    assert not set(prepared.columns).intersection(SIMULATOR_ONLY_FIELDS)


class FeatureContractTests(unittest.TestCase):
    def test_offline_streaming_parity(self):
        test_offline_and_streaming_features_match_for_same_sequence()

    def test_per_robot_history(self):
        test_robot_histories_are_independent()

    def test_current_in_five_sample_windows(self):
        test_five_sample_windows_include_current_observation()

    def test_battery_signs(self):
        test_battery_decline_and_rate_are_positive_for_declining_values()

    def test_warmup_readiness(self):
        test_prediction_waits_for_four_prior_observations()

    def test_deployable_risk_schema(self):
        test_risk_model_schema_contains_only_deployable_features()

    def test_prediction_schema_order(self):
        test_prediction_input_uses_trained_order_and_drops_other_fields()
