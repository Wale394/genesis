"""Regression coverage for fixed-horizon supervised-label eligibility."""

import ast
import random
import unittest
from pathlib import Path

from dataset_generator import DatasetGenerator
from feature_contract import DEPLOYABLE_FEATURES
from feature_engineering import FeatureEngineer
from label_generator import (
    LabelGenerator,
    is_supervised_training_eligible,
    supervised_training_eligibility_mask,
)


def trajectory(robot_id, length, failures=()):
    failures = set(failures)
    return [
        {
            "robot_id": robot_id,
            "time_step": step,
            "manufacturer": "Test Robotics",
            "robot_type": "AMR",
            "motor_temperature": 30.0 + step,
            "ambient_temperature": 20.0,
            "workload": 55.0,
            "battery_level": 100.0 - step,
            "battery_voltage": 48.0 - step * 0.1,
            "battery_current": 10.0 + step,
            "battery_temperature": 25.0 + step * 0.1,
            "power_consumption": 400.0 + step * 4,
            "voltage_drop": step * 0.1,
            "failure_event": step in failures,
            "failure_type": "thermal" if step in failures else "none",
        }
        for step in range(1, length + 1)
    ]


def row_map(rows):
    return {(row["robot_id"], row["time_step"]): row for row in rows}


class LabelEligibilityTests(unittest.TestCase):
    def test_01_complete_positive_horizon_is_eligible(self):
        labeled = LabelGenerator(prediction_window=10).create_labels(
            trajectory("A", 11, failures={8})
        )
        first = row_map(labeled)[("A", 1)]
        self.assertTrue(first["horizon_valid"])
        self.assertEqual(first["label"], 1)
        self.assertTrue(is_supervised_training_eligible(first))

    def test_02_complete_negative_horizon_is_eligible(self):
        labeled = LabelGenerator(prediction_window=10).create_labels(
            trajectory("A", 11)
        )
        first = row_map(labeled)[("A", 1)]
        self.assertTrue(first["horizon_valid"])
        self.assertEqual(first["label"], 0)
        self.assertTrue(is_supervised_training_eligible(first))

    def test_03_incomplete_horizon_is_unknown_and_ineligible(self):
        labeled = LabelGenerator(prediction_window=10).create_labels(
            trajectory("A", 10, failures={10})
        )
        first = row_map(labeled)[("A", 1)]
        self.assertFalse(first["horizon_valid"])
        self.assertIsNone(first["label"])
        self.assertIsNone(first["failure_type_label"])
        self.assertFalse(is_supervised_training_eligible(first))

    def test_04_trailing_horizons_are_scoped_to_each_robot(self):
        # Interleaving makes a dataset-global "next N rows" implementation
        # incorrectly borrow the other robot's records.
        raw = []
        for step in (3, 1, 2):
            raw.append(trajectory("A", 3, failures={2})[step - 1])
            raw.append(trajectory("B", 3)[step - 1])
        labeled = row_map(LabelGenerator(prediction_window=2).create_labels(raw))

        self.assertTrue(labeled[("A", 1)]["horizon_valid"])
        self.assertEqual(labeled[("A", 1)]["label"], 1)
        self.assertTrue(labeled[("B", 1)]["horizon_valid"])
        self.assertEqual(labeled[("B", 1)]["label"], 0)
        for robot_id in ("A", "B"):
            for step in (2, 3):
                self.assertFalse(labeled[(robot_id, step)]["horizon_valid"])
                self.assertIsNone(labeled[(robot_id, step)]["label"])

    def test_05_feature_and_training_selection_never_admit_unknown_negatives(self):
        raw = trajectory("A", 20, failures={18}) + trajectory("B", 20)
        labeled = LabelGenerator(prediction_window=10).create_labels(raw)
        featured = FeatureEngineer().create_features(labeled)
        complete_features = [
            row for row in featured
            if all(row.get(name) is not None for name in DEPLOYABLE_FEATURES)
        ]
        eligibility = supervised_training_eligibility_mask(complete_features)
        training_rows = [row for row, allowed in zip(complete_features, eligibility) if allowed]

        self.assertTrue(training_rows)
        self.assertTrue(all(row["label"] in (0, 1) for row in training_rows))
        self.assertTrue(all(row["horizon_valid"] for row in training_rows))
        self.assertFalse(any(
            row["label"] == 0 and not row["horizon_valid"]
            for row in training_rows
        ))
        self.assertTrue(any(
            row["label"] is None and not row["horizon_valid"]
            for row in complete_features
        ))

    def test_06_normal_and_validation_training_call_the_same_eligibility_rule(self):
        path = Path(__file__).with_name("train_model.py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        required_methods = {"prepare_data", "fit_for_validation", "train_diagnosis_model"}
        methods = {
            node.name: node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for method_name in required_methods:
            calls = [
                node for node in ast.walk(methods[method_name])
                if isinstance(node, ast.Name)
                and node.id == "supervised_training_eligibility_mask"
            ]
            self.assertTrue(calls, f"{method_name} must use shared horizon eligibility")

        rows = LabelGenerator(prediction_window=2).create_labels(
            trajectory("A", 4, failures={3})
        )
        normal_eligible = {
            row["time_step"] for row, allowed in zip(
                rows, supervised_training_eligibility_mask(rows)
            ) if allowed
        }
        validation_eligible = {
            row["time_step"] for row, allowed in zip(
                rows, supervised_training_eligibility_mask(rows)
            ) if allowed
        }
        self.assertEqual(normal_eligible, validation_eligible)

    def test_07_raw_records_are_retained_without_supervision_fields(self):
        raw = trajectory("A", 12, failures={11})
        original_length = len(raw)
        labeled = LabelGenerator(prediction_window=10).create_labels(raw)

        self.assertEqual(len(raw), original_length)
        self.assertNotIn("label", raw[-1])
        self.assertNotIn("horizon_valid", raw[-1])
        self.assertEqual(len(labeled), original_length)
        self.assertFalse(labeled[-1]["horizon_valid"])
        self.assertIsNone(labeled[-1]["label"])

    def test_08_exact_horizon_boundary_and_one_row_short(self):
        exact = LabelGenerator(prediction_window=10).create_labels(
            trajectory("A", 11, failures={11})
        )
        exact_first = row_map(exact)[("A", 1)]
        self.assertEqual(exact_first["future_observations"], 10)
        self.assertTrue(exact_first["horizon_valid"])
        self.assertEqual(exact_first["label"], 1)

        one_short = LabelGenerator(prediction_window=10).create_labels(
            trajectory("A", 10)
        )
        short_first = row_map(one_short)[("A", 1)]
        self.assertEqual(short_first["future_observations"], 9)
        self.assertFalse(short_first["horizon_valid"])
        self.assertIsNone(short_first["label"])
        self.assertFalse(is_supervised_training_eligible(short_first))

    def test_09_main_generator_counts_complete_and_censored_rows(self):
        # Match main.py's deterministic generation settings without writing
        # raw data or fitting either model.
        rng_state = random.getstate()
        random.seed(42)
        try:
            raw = DatasetGenerator(
                number_of_robots=100,
                time_steps=100,
                output_path=None,
            ).generate()
        finally:
            random.setstate(rng_state)
        labeled = LabelGenerator(prediction_window=10).create_labels(raw)
        eligible = [row for row in labeled if is_supervised_training_eligible(row)]
        excluded = [row for row in labeled if not is_supervised_training_eligible(row)]

        self.assertEqual(len(raw), 10_000)
        self.assertEqual(len(eligible), 9_000)
        self.assertEqual(len(excluded), 1_000)
        self.assertEqual(sum(row["label"] == 1 for row in eligible), 612)
        self.assertEqual(sum(row["label"] == 0 for row in eligible), 8_388)
        self.assertTrue(all(row["label"] is None for row in excluded))
        self.assertTrue(all(row["horizon_valid"] is False for row in excluded))


if __name__ == "__main__":
    unittest.main()
