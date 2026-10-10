from measurement_disagreement_experiment import Measurement, Assessment, compare_measurements


def make(sensor, signal, value, location, **kw):
    return Measurement(sensor, signal, value, 10, location, **kw)


CASES = [
    ("robotics", "motor_temperature", "motor_A", 70, 92),
    ("energy", "transformer_temperature", "transformer_A", 70, 92),
    ("industrial", "bearing_temperature", "pump_A", 70, 92),
]


def test_cross_domain_strong_disagreement_requires_investigation():
    for _, signal, location, a_value, b_value in CASES:
        result = compare_measurements(
            make("A", signal, a_value, location),
            make("B", signal, b_value, location),
        )
        assert result["assessment"] == Assessment.MEASUREMENT_CONFLICT.value
        assert result["investigation_required"] is True
        assert result["investigation_target"] == "measurement_system_or_physical_asset"


def test_cross_domain_agreement_supports_without_forcing_domain_semantics():
    for _, signal, location, _, _ in CASES:
        result = compare_measurements(
            make("A", signal, 70, location),
            make("B", signal, 71, location),
        )
        assert result["assessment"] == Assessment.SUPPORTING.value


def test_cross_domain_different_locations_are_contextual():
    for _, signal, location, _, _ in CASES:
        result = compare_measurements(
            make("A", signal, 92, location),
            make("B", signal, 70, f"{location}_secondary"),
        )
        assert result["assessment"] == Assessment.CONTEXTUAL_DIFFERENCE.value


def test_cross_domain_stale_measurement_is_temporal():
    for _, signal, location, _, _ in CASES:
        result = compare_measurements(
            make("A", signal, 92, location),
            make("B", signal, 70, location, freshness="STALE"),
        )
        assert result["assessment"] == Assessment.TEMPORAL_CONFLICT.value


def test_cross_domain_invalid_measurement_is_not_equal_evidence():
    for _, signal, location, _, _ in CASES:
        result = compare_measurements(
            make("A", signal, 92, location),
            make("B", signal, 70, location, validity="INVALID"),
        )
        assert result["assessment"] == Assessment.INVALID_MEASUREMENT.value
