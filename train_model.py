import pandas as pd
from feature_contract import DEPLOYABLE_FEATURES, DIAGNOSIS_FEATURES
from label_generator import supervised_training_eligibility_mask

from sklearn.model_selection import GroupShuffleSplit
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score


class ReliabilityModel:
    def __init__(self, feature_dataset):
        self.data = pd.DataFrame(feature_dataset)
        self.model = None
        self.diagnosis_model = None
        self.model1_test_index = None

    @staticmethod
    def _feature_types(X):
        # These are categorical. Workload is intentionally numeric.
        categorical_features = ["manufacturer", "robot_type"]
        numerical_features = [
            column for column in X.columns
            if column not in categorical_features
        ]
        return categorical_features, numerical_features

    @classmethod
    def _build_preprocessor(cls, X):
        categorical_features, numerical_features = cls._feature_types(X)
        return ColumnTransformer(
            transformers=[
                (
                    "categorical",
                    OneHotEncoder(handle_unknown="ignore"),
                    categorical_features
                ),
                ("numerical", "passthrough", numerical_features)
            ]
        )

    def prepare_data(self):
        missing = [
            feature for feature in DEPLOYABLE_FEATURES
            if feature not in self.data.columns
        ]
        if missing:
            raise ValueError(
                "Training data is missing deployable features: "
                + ", ".join(missing)
            )
        if "horizon_valid" not in self.data.columns:
            raise ValueError(
                "Training data is missing horizon_valid; rebuild labels before fitting."
            )

        eligible = pd.Series(
            supervised_training_eligibility_mask(
                self.data.to_dict(orient="records")
            ),
            index=self.data.index,
        )
        training_data = self.data.loc[eligible]
        horizon_excluded = len(self.data) - len(training_data)
        X = training_data.loc[:, list(DEPLOYABLE_FEATURES)]
        ready = X.notna().all(axis=1)
        X = X.loc[ready]
        training_data = training_data.loc[ready]
        y = training_data["label"]
        groups = training_data["robot_id"]
        print(
            "\nRows excluded for incomplete horizon or unknown target:",
            horizon_excluded,
        )
        print(
            "Rows excluded for missing deployable features:",
            eligible.sum() - len(training_data),
        )
        print("\nFinal model features:")
        print(X.columns.tolist())
        return X, y, groups

    def train(self):
        X, y, groups = self.prepare_data()

        splitter = GroupShuffleSplit(
            n_splits=1, test_size=0.2, random_state=42
        )
        train_index, test_index = next(
            splitter.split(X, y, groups=groups)
        )
        # Keep original dataset positions for main.build_test_set, even though
        # warm-up rows were removed from the trainable feature frame.
        self.model1_test_index = X.index[test_index].tolist()

        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]

        self.model = Pipeline(
            steps=[
                ("preprocessor", self._build_preprocessor(X_train)),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=100,
                        random_state=42,
                        class_weight="balanced"
                    )
                )
            ]
        )

        print("\n========================================")
        print("MODEL 1: FAILURE RISK")
        print("========================================")
        print("\nTraining model...")
        self.model.fit(X_train, y_train)
        print("Training complete.")

        predictions = self.model.predict(X_test)
        probabilities = self.model.predict_proba(X_test)[:, 1]

        print("\nClassification Report:")
        print(classification_report(y_test, predictions))
        print("\nConfusion Matrix:")
        print(confusion_matrix(y_test, predictions))
        print("\nROC-AUC:", round(roc_auc_score(y_test, probabilities), 4))
        print("\nFalse negatives:", ((y_test == 1) & (predictions == 0)).sum())
        print("False positives:", ((y_test == 0) & (predictions == 1)).sum())
        print("\nTraining records:", len(X_train))
        print("Testing records:", len(X_test))

        classifier = self.model.named_steps["classifier"]
        preprocessor = self.model.named_steps["preprocessor"]
        feature_names = preprocessor.get_feature_names_out()
        feature_importance = sorted(
            zip(feature_names, classifier.feature_importances_),
            key=lambda x: x[1],
            reverse=True
        )

        print("\nTop Feature Importances:")
        for feature, importance in feature_importance[:10]:
            print(f"{feature}: {importance:.4f}")

        self.train_diagnosis_model()
        return self.model

    def fit_for_validation(self):
        """Fit the unchanged classifiers on this instance's training data only.

        This validation-only entry point deliberately does not create an
        internal split. The experiment harness passes only its designated
        training records here and evaluates on a separate dataset afterward.
        The estimator and preprocessing settings match ``train``.
        """
        if "horizon_valid" not in self.data.columns:
            raise ValueError(
                "Validation training data must include horizon_valid flags."
            )
        valid_horizon = pd.Series(
            supervised_training_eligibility_mask(
                self.data.to_dict(orient="records")
            ),
            index=self.data.index,
        )
        risk_data = self.data.loc[valid_horizon]
        missing = [
            feature for feature in DEPLOYABLE_FEATURES
            if feature not in risk_data.columns
        ]
        if missing:
            raise ValueError(
                "Training data is missing deployable features: "
                + ", ".join(missing)
            )
        X = risk_data.loc[:, list(DEPLOYABLE_FEATURES)]
        ready = X.notna().all(axis=1)
        risk_data, X = risk_data.loc[ready], X.loc[ready]
        y = risk_data["label"]
        if y.nunique() < 2:
            raise ValueError("Validation training data must contain both risk classes.")

        self.model = Pipeline(steps=[
            ("preprocessor", self._build_preprocessor(X)),
            ("classifier", RandomForestClassifier(
                n_estimators=100,
                random_state=42,
                class_weight="balanced",
            )),
        ])
        self.model.fit(X, y)
        self.validation_risk_training_robot_ids = frozenset(
            risk_data["robot_id"].astype(str)
        )

        diagnosis_data = risk_data[
            (risk_data["label"] == 1)
            & (risk_data["failure_type_label"] != "none")
        ]
        diagnosis_X = diagnosis_data.loc[:, list(DIAGNOSIS_FEATURES)]
        diagnosis_ready = diagnosis_X.notna().all(axis=1)
        diagnosis_data = diagnosis_data.loc[diagnosis_ready]
        diagnosis_X = diagnosis_X.loc[diagnosis_ready]
        diagnosis_y = diagnosis_data["failure_type_label"]
        if diagnosis_y.nunique() < 2:
            raise ValueError(
                "Validation training data must include thermal and battery failures."
            )

        self.diagnosis_model = Pipeline(steps=[
            ("preprocessor", self._build_preprocessor(diagnosis_X)),
            ("classifier", RandomForestClassifier(
                n_estimators=100,
                random_state=42,
                class_weight="balanced",
            )),
        ])
        self.diagnosis_model.fit(diagnosis_X, diagnosis_y)
        self.validation_diagnosis_training_robot_ids = frozenset(
            diagnosis_data["robot_id"].astype(str)
        )
        return self.model, self.diagnosis_model

    def train_diagnosis_model(self):
        if "horizon_valid" not in self.data.columns:
            raise ValueError(
                "Diagnosis training data is missing horizon_valid; rebuild labels before fitting."
            )
        valid_horizon = pd.Series(
            supervised_training_eligibility_mask(
                self.data.to_dict(orient="records")
            ),
            index=self.data.index,
        )
        diagnosis_data = self.data.loc[
            valid_horizon & (self.data["label"] == 1)
        ].copy()
        diagnosis_data = diagnosis_data[
            diagnosis_data["failure_type_label"] != "none"
        ].copy()

        print("\n========================================")
        print("MODEL 2: FAILURE DIAGNOSIS")
        print("========================================")
        print("\nDiagnosis records:", len(diagnosis_data))
        print("\nFailure type distribution:")
        print(diagnosis_data["failure_type_label"].value_counts())

        missing = [
            feature for feature in DIAGNOSIS_FEATURES
            if feature not in diagnosis_data.columns
        ]
        if missing:
            raise ValueError(
                "Diagnosis data is missing deployable features: "
                + ", ".join(missing)
            )

        X = diagnosis_data.loc[:, list(DIAGNOSIS_FEATURES)]
        ready = X.notna().all(axis=1)
        diagnosis_data = diagnosis_data.loc[ready]
        X = X.loc[ready]
        y = diagnosis_data["failure_type_label"]
        groups = diagnosis_data["robot_id"]

        splitter = GroupShuffleSplit(
            n_splits=1, test_size=0.2, random_state=42
        )
        train_index, test_index = next(
            splitter.split(X, y, groups=groups)
        )

        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]

        self.diagnosis_model = Pipeline(
            steps=[
                ("preprocessor", self._build_preprocessor(X_train)),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=100,
                        random_state=42,
                        class_weight="balanced"
                    )
                )
            ]
        )

        print("\nTraining diagnosis model...")
        self.diagnosis_model.fit(X_train, y_train)
        print("Diagnosis model training complete.")

        predictions = self.diagnosis_model.predict(X_test)
        print("\nDiagnosis Classification Report:")
        print(classification_report(y_test, predictions))
        print("\nDiagnosis Confusion Matrix:")
        print(confusion_matrix(y_test, predictions))
        print("\nDiagnosis training records:", len(X_train))
        print("Diagnosis testing records:", len(X_test))

        classifier = self.diagnosis_model.named_steps["classifier"]
        preprocessor = self.diagnosis_model.named_steps["preprocessor"]
        feature_names = preprocessor.get_feature_names_out()
        feature_importance = sorted(
            zip(feature_names, classifier.feature_importances_),
            key=lambda x: x[1],
            reverse=True
        )

        print("\nTop Diagnosis Feature Importances:")
        for feature, importance in feature_importance[:10]:
            print(f"{feature}: {importance:.4f}")
