import unittest

from feature_contract import DEPLOYABLE_FEATURES
from label_generator import LabelGenerator
from prediction_engine import PredictionEngine
from train_model import ReliabilityModel
from validation_experiment import (
    build_dataset,
    build_seed_dataset,
    evaluate_dataset,
    evaluate_events,
)


def model_row(robot_id, step, label=0, failure_type="none",
              horizon_valid=True, failure_event=False):
    row = {
        name: (f"maker-{step % 2}" if name == "manufacturer"
               else "AMR" if name == "robot_type"
               else float(step))
        for name in DEPLOYABLE_FEATURES
    }
    row.update({
        "robot_id": robot_id,
        "time_step": step,
        "label": label,
        "failure_type_label": failure_type,
        "failure_type": failure_type,
        "failure_event": failure_event,
        "horizon_valid": horizon_valid,
    })
    return row


class ConstantRiskModel:
    classes_ = [0, 1]

    def predict(self, values):
        return [0] * len(values)

    def predict_proba(self, values):
        return [[0.8, 0.2] for _ in range(len(values))]


class ValidationHarnessTests(unittest.TestCase):
    def test_horizon_invalid_rows_are_censored_not_confirmed_negatives(self):
        raw = [
            {"robot_id": "R1", "time_step": step, "failure_event": False}
            for step in range(1, 5)
        ]
        labeled = LabelGenerator(prediction_window=2).create_labels(raw)
        self.assertTrue(labeled[0]["horizon_valid"])
        self.assertFalse(labeled[2]["horizon_valid"])
        self.assertFalse(labeled[3]["horizon_valid"])
        self.assertIsNone(labeled[3]["label"])

    def test_training_and_test_datasets_are_disjoint(self):
        train = build_seed_dataset(
            [42], "TRAIN", number_of_robots=2, time_steps=12
        )
        test = build_seed_dataset(
            [100], "BASELINE", number_of_robots=2, time_steps=12
        )
        train_ids = {row["robot_id"] for row in train}
        test_ids = {row["robot_id"] for row in test}
        self.assertTrue(train_ids)
        self.assertTrue(test_ids)
        self.assertTrue(train_ids.isdisjoint(test_ids))

    def test_test_scenario_rows_never_enter_model_fitting(self):
        training_rows = []
        for robot_index in range(8):
            robot_id = f"TRAIN-{robot_index}"
            for step in range(6):
                if step < 3:
                    label, kind = 0, "none"
                else:
                    label = 1
                    kind = "thermal" if robot_index % 2 else "battery"
                training_rows.append(model_row(
                    robot_id, step, label, kind, True
                ))
        training_rows.append(model_row(
            "CENSORED-ONLY", 99, 0, "none", False
        ))
        test_rows = [
            model_row(f"TEST-{i}", i, 0, "none", True)
            for i in range(4)
        ]
        trainer = ReliabilityModel(training_rows)
        trainer.fit_for_validation()
        test_ids = {row["robot_id"] for row in test_rows}
        self.assertTrue(
            trainer.validation_risk_training_robot_ids.isdisjoint(test_ids)
        )
        self.assertTrue(
            trainer.validation_diagnosis_training_robot_ids.isdisjoint(test_ids)
        )
        self.assertEqual(
            trainer.validation_risk_training_robot_ids,
            {row["robot_id"] for row in training_rows
             if row["horizon_valid"]},
        )
        self.assertNotIn(
            "CENSORED-ONLY", trainer.validation_risk_training_robot_ids
        )

    def test_scenario_parameters_change_generated_telemetry(self):
        standard = build_dataset(
            314, "STANDARD", number_of_robots=3, time_steps=25
        )
        high = build_dataset(
            314,
            "SUSTAINED_HIGH",
            {"workload_mode": "sustained_high"},
            number_of_robots=3,
            time_steps=25,
        )
        standard_by_robot = {
            (row["robot_id"].split("-")[-1], row["time_step"]): row
            for row in standard
        }
        high_by_robot = {
            (row["robot_id"].split("-")[-1], row["time_step"]): row
            for row in high
        }
        self.assertNotEqual(
            standard_by_robot[("R001", 25)]["workload"],
            high_by_robot[("R001", 25)]["workload"],
        )

    def test_event_warning_counts_each_actual_failure_once(self):
        rows = [
            model_row(
                "R1", step, failure_event=(step == 10),
                horizon_valid=True,
            )
            for step in range(1, 13)
        ]
        probabilities = [
            0.1 if step < 2 else 0.4
            for step in range(1, 13)
        ]
        result = evaluate_events(rows, probabilities)
        self.assertEqual(result["total_actual_failures"], 1)
        self.assertEqual(result["failures_warned_before_event"], 1)
        self.assertEqual(result["missed_failures"], 0)

    def test_censored_rows_are_excluded_from_fixed_horizon_metrics(self):
        valid = model_row("R1", 1, horizon_valid=True)
        censored = model_row("R1", 2, horizon_valid=False)
        result = evaluate_dataset(
            ConstantRiskModel(),
            diagnosis_model=None,
            rows=[valid, censored],
        )
        self.assertEqual(result["valid_records"], 1)
        self.assertEqual(result["censored_records"], 1)
        self.assertEqual(result["risk"]["records"], 1)

    def test_feature_schema_is_identical_across_scenarios(self):
        baseline = build_dataset(
            271, "BASELINE", number_of_robots=3, time_steps=25
        )
        shifted = build_dataset(
            271,
            "THERMAL_SHIFT",
            {
                "thermal_failure_threshold": 86.0,
                "thermal_degradation_scale": 0.75,
            },
            number_of_robots=3,
            time_steps=25,
        )
        for dataset in (baseline, shifted):
            self.assertTrue(dataset)
            self.assertTrue(all(
                all(name in row for name in DEPLOYABLE_FEATURES)
                for row in dataset
            ))

        training_rows = []
        for robot_index in range(8):
            for step in range(6):
                label = int(step >= 3)
                kind = (
                    "thermal" if robot_index % 2 else "battery"
                ) if label else "none"
                training_rows.append(model_row(
                    f"SCHEMA-TRAIN-{robot_index}", step, label, kind, True
                ))
        trainer = ReliabilityModel(training_rows)
        risk_model, _ = trainer.fit_for_validation()
        self.assertEqual(
            list(risk_model.feature_names_in_), list(DEPLOYABLE_FEATURES)
        )
        engine = PredictionEngine(risk_model)
        for dataset in (baseline, shifted):
            prepared = engine._prepare_input([dataset[10]])
            self.assertEqual(list(prepared.columns), list(DEPLOYABLE_FEATURES))


if __name__ == "__main__":
    unittest.main()
