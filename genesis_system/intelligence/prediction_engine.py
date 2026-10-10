import pandas as pd
from feature_contract import DEPLOYABLE_FEATURES


class PredictionEngine:

    # Public schema alias; EXCLUDED_COLUMNS remains for older callers.
    FEATURE_ALLOWLIST = DEPLOYABLE_FEATURES
    EXCLUDED_COLUMNS = [
        "label",
        "failure_type_label",
        "failure_type",
        "failure_event",
        "recovery_event",
        "health",
        "initial_health",
        "robot_id",
        "time_step",
        "robot_state",
        "battery_health",
        "battery_stress",
        "degradation_level",
    ]

    def __init__(self, model):
        self.model = model

    def _prepare_input(self, feature_records):

        input_data = pd.DataFrame(feature_records)

        missing_features = [
            feature for feature in DEPLOYABLE_FEATURES
            if feature not in input_data.columns
        ]
        if missing_features:
            raise ValueError(
                "Missing features required by the deployable contract: "
                + ", ".join(missing_features)
            )

        expected_features = list(
            getattr(self.model, "feature_names_in_", DEPLOYABLE_FEATURES)
        )
        unexpected_features = [
            feature for feature in expected_features
            if feature not in DEPLOYABLE_FEATURES
        ]
        if unexpected_features:
            raise ValueError(
                "The trained model expects features outside the deployable "
                "contract: " + ", ".join(unexpected_features)
            )
        input_data = input_data[expected_features]

        unavailable = input_data.columns[input_data.isna().any()].tolist()
        if unavailable:
            raise ValueError(
                "Prediction features are unavailable or still warming up: "
                + ", ".join(unavailable)
            )

        return input_data

    def predict(self, feature_record):

        input_data = self._prepare_input(
            [feature_record]
        )

        prediction = self.model.predict(
            input_data
        )[0]

        probability = self.model.predict_proba(
            input_data
        )[0][1]

        return {
            "prediction": int(prediction),
            "probability": float(round(probability, 4))
        }

    def predict_batch(self, feature_records):

        input_data = self._prepare_input(
            feature_records
        )

        predictions = self.model.predict(input_data)

        probabilities = self.model.predict_proba(
            input_data
        )[:, 1]

        results = []

        for prediction, probability in zip(
            predictions,
            probabilities
        ):
            results.append({
                "prediction": int(prediction),
                "probability": float(round(probability, 4))
            })

        return results

    def get_required_features(self):

        if not hasattr(self.model, "feature_names_in_"):
            raise ValueError(
                "The trained model does not expose "
                "feature_names_in_."
            )

        return list(self.model.feature_names_in_)
