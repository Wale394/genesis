import math
from numbers import Real

from reliability_signal import ReliabilitySignal
from observation_quality import ObservationQuality


class ReliabilityFusion:

    def __init__(self, signal_engine=None):

        self.signal_engine = (
            signal_engine
            if signal_engine is not None
            else ReliabilitySignal()
        )
        self.observation_quality_engine = ObservationQuality()

    def evaluate(
        self,
        feature_record,
        ml_probability,
        ml_prediction,
        observation_quality=None,
        historical_records=None,
    ):

        if observation_quality is None:
            observation_quality = self.observation_quality_engine.assess(
                feature_record, historical_records
            )

        signal_record = dict(feature_record)
        for field in (
            "battery_level", "battery_change", "motor_temperature",
            "thermal_rise", "voltage_drop", "battery_current",
        ):
            value = signal_record.get(field)
            if value is not None and (
                not isinstance(value, Real)
                or isinstance(value, bool)
                or not math.isfinite(float(value))
            ):
                signal_record[field] = None
        signal_result = self.signal_engine.analyze(signal_record)

        engineering_severity = (
            signal_result["severity"]
        )

        # ----------------------------------------------------
        # FINAL PREDICTION
        # ----------------------------------------------------

        final_prediction = ml_prediction

        # A critical engineering signal overrides
        # an ML prediction of "no failure".
        if engineering_severity == "critical":

            final_prediction = 1

        # ----------------------------------------------------
        # FINAL RISK
        # ----------------------------------------------------

        if engineering_severity == "critical":

            final_risk = "CRITICAL"

        elif ml_probability is None:

            # A missing model score cannot establish health.
            final_risk = "WATCH"

        elif (
            ml_probability >= 0.90
        ):

            final_risk = "CRITICAL"

        elif (
            ml_probability >= 0.70
        ):

            final_risk = "WARNING"

        elif (
            ml_probability >= 0.30
            or engineering_severity == "warning"
        ):

            final_risk = "WATCH"

        else:

            final_risk = "HEALTHY"

        quality_limited = bool(
            observation_quality
            and observation_quality.get("status") != "AVAILABLE"
        )
        if quality_limited and final_risk == "HEALTHY":
            # Preserve all model and engineering thresholds. Limited evidence
            # prevents a healthy interpretation; it does not assert failure.
            final_risk = "WATCH"

        if final_prediction == 1 and final_risk == "HEALTHY":
            final_risk = "WATCH"

        # ----------------------------------------------------
        # RETURN BOTH SOURCES
        # ----------------------------------------------------

        return {
            "ml": {
                "probability": ml_probability,
                "prediction": ml_prediction
            },

            "engineering": signal_result,
            "observation_quality": observation_quality,

            "final": {
                "prediction": final_prediction,
                "risk": final_risk,
                "confidence_limited": quality_limited,
            }
        }
