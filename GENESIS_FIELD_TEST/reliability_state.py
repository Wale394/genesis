class ReliabilityState:

    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"

    def transition_from_fusion(
        self,
        fusion_result,
        previous_state=None,
        observation_quality=None,
        actual_failure=False,
        recovery_event=False,
    ):
        """Apply lifecycle transitions to Fusion's already-classified risk."""
        if actual_failure:
            return self.FAILED

        if previous_state == self.FAILED:
            return self.RECOVERING if recovery_event else self.FAILED

        final = fusion_result.get("final", {})
        risk = final.get("risk", "WATCH")
        prediction = final.get("prediction")
        quality_available = bool(
            observation_quality
            and observation_quality.get("status") == "AVAILABLE"
        )

        if previous_state == self.RECOVERING:
            if risk == "HEALTHY" and prediction == 0 and quality_available:
                return self.HEALTHY
            return self.RECOVERING

        if previous_state == self.CRITICAL and prediction == 0:
            return self.RECOVERING

        state_by_risk = {
            "HEALTHY": self.HEALTHY,
            "WATCH": self.WATCH,
            "WARNING": self.WARNING,
            "CRITICAL": self.CRITICAL,
        }
        return state_by_risk.get(risk, self.WATCH)

    def determine_state(
        self,
        probability,
        prediction,
        previous_state=None,
        observation_quality=None,
    ):

        quality_limited = bool(
            observation_quality
            and observation_quality.get("status") != "AVAILABLE"
        )

        if prediction is None:
            if previous_state in [self.CRITICAL, self.FAILED, self.RECOVERING]:
                return previous_state
            return self.WATCH

        if prediction == 0:

            if previous_state in [
                self.CRITICAL,
                self.FAILED
            ]:
                return self.RECOVERING

            if quality_limited or probability >= 0.15:
                return self.WATCH

            return self.HEALTHY

        if probability >= 0.90:
            return self.CRITICAL

        if probability >= 0.70:
            return self.WARNING

        if probability >= 0.30:
            return self.WATCH

        return self.HEALTHY
