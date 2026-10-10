import contextlib
import io
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from diagnosis_engine import DiagnosisEngine
from feature_contract import (
    DIAGNOSIS_FEATURES,
    SIMULATOR_ONLY_FIELDS,
)
from label_generator import LabelGenerator
from telemetry_features import TelemetryFeatureBuilder
from train_model import ReliabilityModel


def telemetry_snapshot(robot_id, step):
    return {
        "identity": {
            "robot_id": robot_id,
            "manufacturer": "Test Robotics",
            "robot_type": "AMR",
        },
        "telemetry": {
            "time_step": step,
            "motor_temperature": 30.0 + step * 2,
            "ambient_temperature": 20.0,
            "battery_level": 100.0 - step * 3,
            "battery_voltage": 48.0 - step * 0.2,
            "battery_current": 8.0 + step * 0.4,
            "battery_temperature": 25.0 + step * 0.3,
            "power_consumption": 400.0 + step * 5,
            "voltage_drop": step * 0.1,
            "workload": 50.0,
        },
    }


class RecordingModel:
    def __init__(self, columns):
        self.feature_names_in_ = columns
        self.seen_columns = None

    def predict(self, values):
        self.seen_columns = list(values.columns)
        return ["thermal"]


class DiagnosisContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path("data/feature_dataset.csv")
        if not path.exists():
            raise unittest.SkipTest("Existing labeled feature dataset is unavailable")
        dataset = pd.read_csv(path)
        cls.rows = dataset.to_dict(orient="records")

        # The checked-in CSV predates persisted horizon_valid metadata.
        # Recompute the current fixed-horizon eligibility from its paired raw
        # simulator rows rather than assuming missing horizons are complete.
        raw_path = Path("data/raw_dataset_v2.csv")
        raw = pd.read_csv(raw_path).to_dict(orient="records")
        for row in raw:
            row["time_step"] = int(row["time_step"])
            row["failure_event"] = str(row["failure_event"]).lower() == "true"
        labeled = LabelGenerator().create_labels(raw)
        eligibility = {
            (row["robot_id"], int(row["time_step"])): row
            for row in labeled
        }
        for row in cls.rows:
            target = eligibility[(row["robot_id"], int(row["time_step"]))]
            row["horizon_valid"] = target["horizon_valid"]
            if not target["horizon_valid"]:
                row["label"] = None
                row["failure_type_label"] = None

        cls.trainer = ReliabilityModel(cls.rows)
        with contextlib.redirect_stdout(io.StringIO()):
            cls.trainer.train_diagnosis_model()
        cls.model = cls.trainer.diagnosis_model

    def deployable_record(self):
        builder = TelemetryFeatureBuilder()
        for step in range(1, 6):
            record = builder.build(telemetry_snapshot("robot-normal", step))
        return {name: record[name] for name in DIAGNOSIS_FEATURES}

    def test_training_schema_excludes_simulator_fields(self):
        names = list(self.model.feature_names_in_)
        self.assertEqual(names, list(DIAGNOSIS_FEATURES))
        self.assertFalse(set(names) & SIMULATOR_ONLY_FIELDS)

    def test_inference_accepts_normal_deployable_record(self):
        record = self.deployable_record()
        self.assertFalse(set(record) & SIMULATOR_ONLY_FIELDS)
        result = DiagnosisEngine(self.model).predict_failure_type(record)
        self.assertIn(result, {"thermal", "battery"})

    def test_inference_column_order_matches_training(self):
        record = self.deployable_record()
        spy = RecordingModel(list(self.model.feature_names_in_))
        DiagnosisEngine(spy).predict_failure_type(record)
        self.assertEqual(spy.seen_columns, list(self.model.feature_names_in_))

    def test_absent_simulator_fields_do_not_prevent_diagnosis(self):
        record = self.deployable_record()
        self.assertTrue(SIMULATOR_ONLY_FIELDS.isdisjoint(record))
        self.assertIn(
            DiagnosisEngine(self.model).predict_failure_type(record),
            {"thermal", "battery"},
        )

    def test_held_out_dataset_still_distinguishes_failure_types(self):
        data = pd.DataFrame(self.rows)
        data = data[(data["label"] == 1) & (data["failure_type_label"] != "none")]
        X = data.loc[:, list(DIAGNOSIS_FEATURES)]
        ready = X.notna().all(axis=1)
        data, X = data.loc[ready], X.loc[ready]
        y = data["failure_type_label"]
        train_idx, test_idx = next(GroupShuffleSplit(
            n_splits=1, test_size=0.2, random_state=42
        ).split(X, y, groups=data["robot_id"]))
        truth = y.iloc[test_idx]
        predicted = self.model.predict(X.iloc[test_idx])
        self.assertEqual(set(truth.unique()), {"thermal", "battery"})
        self.assertGreaterEqual((truth.to_numpy() == predicted).mean(), 0.70)


if __name__ == "__main__":
    unittest.main()
