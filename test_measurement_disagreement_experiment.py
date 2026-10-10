from measurement_disagreement_experiment import Measurement, Assessment, compare_measurements


def m(sensor, value, **kw):
    return Measurement(sensor, "motor_temperature", value, 10, kw.pop("location", "motor_A"), **kw)


def test_agreement_supports():
    r = compare_measurements(m("A", 70), m("B", 71))
    assert r["assessment"] == Assessment.SUPPORTING.value


def test_small_disagreement_is_not_conflict():
    r = compare_measurements(m("A", 70), m("B", 73))
    assert r["assessment"] == Assessment.SUPPORTING.value


def test_strong_disagreement_targets_measurement_system_or_asset():
    r = compare_measurements(m("A", 70), m("B", 92))
    assert r["assessment"] == Assessment.MEASUREMENT_CONFLICT.value
    assert r["investigation_required"] is True


def test_stale_measurement_is_temporal_conflict():
    r = compare_measurements(m("A", 92), m("B", 70, freshness="STALE"))
    assert r["assessment"] == Assessment.TEMPORAL_CONFLICT.value


def test_invalid_measurement_is_not_equal_evidence():
    r = compare_measurements(m("A", 92), m("B", 70, validity="INVALID"))
    assert r["assessment"] == Assessment.INVALID_MEASUREMENT.value


def test_different_locations_are_contextual_not_conflicting():
    r = compare_measurements(m("A", 92), m("B", 70, location="motor_B"))
    assert r["assessment"] == Assessment.CONTEXTUAL_DIFFERENCE.value


def test_calibration_unknown_prevents_equal_trust():
    r = compare_measurements(m("A", 92), m("B", 70, calibration="UNKNOWN"))
    assert r["assessment"] == Assessment.INVALID_MEASUREMENT.value


def test_timestamp_difference_is_preserved_as_limitation_when_values_agree():
    b = Measurement("B", "motor_temperature", 71, 11, "motor_A")
    r = compare_measurements(m("A", 70), b)
    assert r["assessment"] == Assessment.SUPPORTING.value
    assert "timestamps differ" in r["limitations"]


def test_unknown_signal_relationship_does_not_create_false_confirmation():
    b = Measurement("B", "bearing_temperature", 70, 10, "motor_A")
    r = compare_measurements(m("A", 92), b)
    assert r["assessment"] == Assessment.INSUFFICIENT_CONTEXT.value


def test_disagreement_does_not_choose_a_winner():
    r = compare_measurements(m("A", 92), m("B", 70))
    assert "winner" not in r
    assert "chosen_sensor" not in r
