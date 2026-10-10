class RecommendationEngine:

    def __init__(self):
        pass

    def determine_risk_level(self, probability):

        if probability >= 0.70:
            return "HIGH"

        elif probability >= 0.30:
            return "MEDIUM"

        else:
            return "LOW"

    def recommend(
        self,
        risk_result,
        diagnosis_result,
        state=None,
        observation_quality=None,
    ):

        failure_probability = risk_result.get("probability")

        # --------------------------------
        # FAILED STATE
        # --------------------------------

        if state == "FAILED":

            return {
                "risk_level": "FAILED",
                "failure_probability": failure_probability,
                "failure_type": (
                    diagnosis_result.get("failure_type")
                    if diagnosis_result is not None
                    else None
                ),
                "probable_cause": (
                    diagnosis_result.get("probable_cause")
                    if diagnosis_result is not None
                    else None
                ),
                "recommendation": (
                    "Robot has failed. Keep it out of normal "
                    "operation and investigate the failure."
                )
            }

        # --------------------------------
        # RECOVERING STATE
        # --------------------------------

        if state == "RECOVERING":

            return {
                "risk_level": "RECOVERING",
                "failure_probability": failure_probability,
                "failure_type": (
                    diagnosis_result.get("failure_type")
                    if diagnosis_result is not None
                    else None
                ),
                "probable_cause": (
                    diagnosis_result.get("probable_cause")
                    if diagnosis_result is not None
                    else None
                ),
                "recommendation": (
                    "Recovery detected. Verify robot stability "
                    "before returning to normal operation."
                )
            }

        state_risk_levels = {
            "HEALTHY": "LOW",
            "WATCH": "MEDIUM",
            "WARNING": "HIGH",
            "CRITICAL": "HIGH",
        }
        if state in state_risk_levels:
            risk_level = state_risk_levels[state]
        elif failure_probability is None:
            risk_level = "MEDIUM"
        else:
            risk_level = self.determine_risk_level(failure_probability)

        failure_type = (
            diagnosis_result.get("failure_type")
            if diagnosis_result is not None
            else None
        )

        probable_cause = (
            diagnosis_result.get("probable_cause")
            if diagnosis_result is not None
            else None
        )

        quality_limited = bool(
            observation_quality
            and observation_quality.get("status") != "AVAILABLE"
        )
        if state == "WATCH" and quality_limited:
            limited_groups = [
                name for name, group in observation_quality.get("groups", {}).items()
                if group.get("status") != "AVAILABLE"
            ]
            recommendation = (
                "Telemetry evidence is limited for "
                + ", ".join(limited_groups)
                + "; verify the relevant sensors and history before treating a low risk score as evidence of health."
            )

        elif risk_level == "LOW":

            recommendation = (
                "Continue normal operation and monitoring."
            )

        elif risk_level == "MEDIUM":

            if failure_type == "thermal":

                recommendation = (
                    "Monitor motor temperature closely "
                    "and consider reducing workload."
                )

            elif failure_type == "battery":

                recommendation = (
                    "Monitor battery condition and "
                    "consider scheduling a battery inspection."
                )

            else:

                recommendation = (
                    "Increase monitoring frequency and "
                    "inspect the robot if the risk continues."
                )

        else:

            if failure_type == "thermal":

                recommendation = (
                    "Reduce workload and inspect the "
                    "robot's thermal management system."
                )

            elif failure_type == "battery":

                recommendation = (
                    "Reduce operation and inspect the "
                    "battery and power system."
                )

            else:

                recommendation = (
                    "Reduce robot workload and perform "
                    "a reliability inspection."
                )

        return {
            "risk_level": risk_level,
            "failure_probability": failure_probability,
            "failure_type": failure_type,
            "probable_cause": probable_cause,
            "recommendation": recommendation
        }
