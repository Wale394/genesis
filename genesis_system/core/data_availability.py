from feature_contract import (
    DEPLOYABLE_FEATURES,
    HISTORY_COUNT_FIELD,
    minimum_history_for,
)


class DataAvailability:
    FEATURE_GROUPS = {
        "deployable_model": list(DEPLOYABLE_FEATURES),
    }

    def inspect(self, feature_record):
        available = []
        unavailable = []
        for key, value in feature_record.items():
            (unavailable if value is None else available).append(key)
        return {
            "available": available,
            "unavailable": unavailable,
            "complete": len(unavailable) == 0,
        }

    def get_required_model_features(self, model):
        if not hasattr(model, "feature_names_in_"):
            raise ValueError(
                "The trained model does not expose feature_names_in_."
            )
        required = list(model.feature_names_in_)
        unexpected = [
            feature for feature in required
            if feature not in DEPLOYABLE_FEATURES
        ]
        if unexpected:
            raise ValueError(
                "The model requires features outside the deployable contract: "
                + ", ".join(unexpected)
            )
        return required

    def can_run_prediction(self, feature_record, model):
        required_features = self.get_required_model_features(model)
        missing_features = [
            feature for feature in required_features
            if feature not in feature_record or feature_record[feature] is None
        ]

        required_history = minimum_history_for(required_features)
        available_history = feature_record.get(HISTORY_COUNT_FIELD)
        history_ready = (
            available_history is not None
            and available_history >= required_history
        )

        missing_categories = []
        if missing_features:
            missing_categories.append("deployable_model")
        if not history_ready:
            missing_categories.append("temporal_warmup")

        return {
            "can_predict": not missing_features and history_ready,
            "required_features": required_features,
            "missing_features": missing_features,
            "missing_categories": missing_categories,
            "history_ready": history_ready,
            "required_history": required_history,
            "available_history": available_history,
        }
