class WarningEngine:

    def __init__(
        self,
        probability_threshold=0.30,
        consecutive_steps=3
    ):
        self.probability_threshold = probability_threshold
        self.consecutive_steps = consecutive_steps

    def evaluate_robot(self, timeline):
        """
        Evaluate one robot's prediction timeline.

        A warning is generated when the model probability
        stays above the threshold for several consecutive steps.
        """

        consecutive_risk = 0

        warning = None

        for point in timeline:

            probability = point["probability"]

            if probability >= self.probability_threshold:

                consecutive_risk += 1

            else:

                consecutive_risk = 0

            if (
                consecutive_risk
                >= self.consecutive_steps
            ):

                warning = {
                    "warning": True,
                    "warning_time": point["time_step"],
                    "probability": probability
                }

                break

        if warning is None:

            return {
                "warning": False,
                "warning_time": None,
                "probability": 0.0
            }

        return warning