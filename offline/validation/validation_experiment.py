"""Out-of-scenario validation for the fixed Genesis feature/model contract."""

import json
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, average_precision_score, brier_score_loss,
    confusion_matrix, f1_score, precision_recall_fscore_support,
    precision_score, recall_score, roc_auc_score,
)

from dataset_generator import DatasetGenerator
from feature_contract import DEPLOYABLE_FEATURES, DIAGNOSIS_FEATURES
from feature_engineering import FeatureEngineer
from fleet_simulator import DEFAULT_SIMULATION_CONFIG
from label_generator import LabelGenerator
from train_model import ReliabilityModel

TRAINING_SEEDS = (42, 43, 44)
BASELINE_TEST_SEEDS = (100, 101)
UNSEEN_TEST_SEEDS = (200, 201, 202)
NUMBER_OF_ROBOTS = 100
TIME_STEPS = 100
PREDICTION_WINDOW = 10
WARNING_THRESHOLD = 0.30
WARNING_STEPS = 2

SCENARIOS = {
    "BASELINE": {
        "test_seeds": BASELINE_TEST_SEEDS,
        "config": {},
        "workload_scenario": "current synchronized workload cycle",
    },
    "UNSEEN_SEEDS": {
        "test_seeds": UNSEEN_TEST_SEEDS,
        "config": {},
        "workload_scenario": "current synchronized workload cycle",
    },
    "THERMAL_SHIFT": {
        "test_seeds": BASELINE_TEST_SEEDS,
        "config": {
            "thermal_failure_threshold": 86.0,
            "thermal_degradation_scale": 0.75,
        },
        "workload_scenario": "current synchronized workload cycle",
    },
    "BATTERY_SHIFT": {
        "test_seeds": BASELINE_TEST_SEEDS,
        "config": {
            "battery_degradation_rate_range": (0.003, 0.008),
            "battery_stress_scale": 1.20,
            "battery_failure_health_threshold": 0.75,
            "battery_failure_stress_threshold": 6.0,
            "battery_failure_level_threshold": 25.0,
        },
        "workload_scenario": "current synchronized workload cycle",
    },
    "WORKLOAD_ASYNCHRONOUS": {
        "test_seeds": BASELINE_TEST_SEEDS,
        "config": {"workload_mode": "asynchronous"},
        "workload_scenario": "asynchronous robot-specific phases",
    },
    "WORKLOAD_SUSTAINED_HIGH": {
        "test_seeds": BASELINE_TEST_SEEDS,
        "config": {"workload_mode": "sustained_high"},
        "workload_scenario": "sustained high",
    },
    "WORKLOAD_SUSTAINED_LOW": {
        "test_seeds": BASELINE_TEST_SEEDS,
        "config": {"workload_mode": "sustained_low"},
        "workload_scenario": "sustained low",
    },
    "WORKLOAD_MIXED": {
        "test_seeds": BASELINE_TEST_SEEDS,
        "config": {
            "workload_mode": "mixed",
            "workload_schedule": ("low", "medium", "high"),
        },
        "workload_scenario": "mixed per-robot workload distribution",
    },
    "TELEMETRY_STRESS": {
        "test_seeds": BASELINE_TEST_SEEDS,
        "config": {
            "telemetry_noise_scale": 2.5,
            "thermal_observation_coupling": 4.0,
            "battery_observation_coupling": 0.4,
            "thermal_failure_uses_observed_temperature": False,
        },
        "workload_scenario": "current synchronized workload cycle",
    },
}


def build_dataset(seed, scenario_name="BASELINE", simulator_config=None,
                  number_of_robots=NUMBER_OF_ROBOTS, time_steps=TIME_STEPS):
    """Create one isolated, named scenario/seed dataset in memory."""
    raw = DatasetGenerator(
        number_of_robots=number_of_robots,
        time_steps=time_steps,
        output_path=None,
        scenario_name=scenario_name,
        seed=seed,
        simulator_config=simulator_config,
    ).generate()
    labeled = LabelGenerator(
        prediction_window=PREDICTION_WINDOW
    ).create_labels(raw)
    featured = FeatureEngineer().create_features(labeled)
    for row in featured:
        row["manufacturer"] = str(row.get("manufacturer") or "unknown")
        row["robot_type"] = str(row.get("robot_type") or "unknown")
        row["scenario_name"] = scenario_name
        row["scenario_seed"] = seed
    return featured


def build_seed_dataset(seeds, scenario_name, simulator_config=None,
                       number_of_robots=NUMBER_OF_ROBOTS,
                       time_steps=TIME_STEPS):
    rows = []
    for seed in seeds:
        rows.extend(build_dataset(
            seed,
            scenario_name=scenario_name,
            simulator_config=simulator_config,
            number_of_robots=number_of_robots,
            time_steps=time_steps,
        ))
    return rows


def _complete_features(rows, features):
    return [
        row for row in rows
        if all(row.get(name) is not None for name in features)
    ]


def _warning_times(timeline):
    """Return one timestamp per threshold episode using the fixed settings."""
    result = []
    consecutive = 0
    active = False
    for item in timeline:
        if not item["horizon_valid"] or item["probability"] is None:
            continue
        if item["probability"] >= WARNING_THRESHOLD:
            consecutive += 1
            if consecutive >= WARNING_STEPS and not active:
                result.append(item["time_step"])
                active = True
        else:
            consecutive = 0
            active = False
    return result


def evaluate_events(rows, probabilities, prediction_rows=None):
    """Count each failure once and attribute at most one alert to that event."""
    probability_rows = prediction_rows if prediction_rows is not None else rows
    probability_by_key = {
        (row["robot_id"], row["time_step"]): float(probability)
        for row, probability in zip(probability_rows, probabilities)
    }
    timelines = defaultdict(list)
    rows_by_robot = defaultdict(list)
    for row in rows:
        rows_by_robot[row["robot_id"]].append(row)
    for robot_id, robot_rows in rows_by_robot.items():
        for row in robot_rows:
            p = probability_by_key.get((robot_id, row["time_step"]))
            timelines[robot_id].append({
                "time_step": row["time_step"],
                "probability": p,
                "horizon_valid": bool(row.get("horizon_valid", False)),
            })
        timelines[robot_id].sort(key=lambda item: item["time_step"])

    event_count = warned_count = missed_count = false_alarms = 0
    lead_times = []
    for robot_id, robot_rows in rows_by_robot.items():
        failures = sorted(
            row["time_step"] for row in robot_rows
            if row.get("failure_event", False)
        )
        event_count += len(failures)
        alert_times = _warning_times(timelines[robot_id])
        used_alerts = set()
        previous_failure = -1
        for failure_time in failures:
            eligible = [
                warning for warning in alert_times
                if warning not in used_alerts
                and previous_failure < warning < failure_time
                and failure_time - PREDICTION_WINDOW <= warning
            ]
            if eligible:
                warning_time = min(eligible)
                used_alerts.add(warning_time)
                warned_count += 1
                lead_times.append(failure_time - warning_time)
            else:
                missed_count += 1
            previous_failure = failure_time
        false_alarms += sum(
            warning not in used_alerts for warning in alert_times
        )

    return {
        "total_actual_failures": event_count,
        "failures_warned_before_event": warned_count,
        "missed_failures": missed_count,
        "false_alarms": false_alarms,
        "warning_coverage": warned_count / event_count if event_count else 0.0,
        "lead_time": {
            "mean": float(np.mean(lead_times)) if lead_times else None,
            "median": float(np.median(lead_times)) if lead_times else None,
            "minimum": min(lead_times) if lead_times else None,
            "maximum": max(lead_times) if lead_times else None,
        },
    }


def evaluate_dataset(model, diagnosis_model, rows):
    horizon_valid_rows = [
        row for row in rows if row.get("horizon_valid") is True
    ]
    risk_rows = _complete_features(horizon_valid_rows, DEPLOYABLE_FEATURES)
    X = pd.DataFrame(
        [{name: row[name] for name in DEPLOYABLE_FEATURES} for row in risk_rows],
        columns=DEPLOYABLE_FEATURES,
    )
    y = np.asarray([int(row["label"]) for row in risk_rows], dtype=int)
    predictions = np.asarray(model.predict(X), dtype=int)
    class_index = list(model.classes_).index(1)
    probabilities = np.asarray(model.predict_proba(X))[:, class_index]
    risk_metrics = {
        "records": len(risk_rows),
        "precision": float(precision_score(y, predictions, zero_division=0)),
        "recall": float(recall_score(y, predictions, zero_division=0)),
        "f1": float(f1_score(y, predictions, zero_division=0)),
        "roc_auc": (
            float(roc_auc_score(y, probabilities))
            if len(np.unique(y)) == 2 else None
        ),
        "pr_auc": (
            float(average_precision_score(y, probabilities))
            if len(np.unique(y)) == 2 else None
        ),
        "confusion_matrix_labels_0_1": confusion_matrix(
            y, predictions, labels=[0, 1]
        ).tolist(),
        "brier_score": float(brier_score_loss(y, probabilities)) if len(y) else None,
    }

    diagnosis_rows = [
        row for row in horizon_valid_rows
        if row.get("label") == 1
        and row.get("failure_type_label") in ("battery", "thermal")
    ]
    diagnosis_rows = _complete_features(diagnosis_rows, DIAGNOSIS_FEATURES)
    if diagnosis_rows:
        diagnosis_X = pd.DataFrame(
            [
                {name: row[name] for name in DIAGNOSIS_FEATURES}
                for row in diagnosis_rows
            ],
            columns=DIAGNOSIS_FEATURES,
        )
        diagnosis_y = np.asarray([
            row["failure_type_label"] for row in diagnosis_rows
        ])
        diagnosis_predictions = diagnosis_model.predict(diagnosis_X)
        class_order = ["battery", "thermal"]
        support = precision_recall_fscore_support(
            diagnosis_y, diagnosis_predictions, labels=class_order,
            zero_division=0,
        )
        diagnosis_metrics = {
            name: {
                "precision": float(support[0][index]),
                "recall": float(support[1][index]),
                "f1": float(support[2][index]),
                "support": int(support[3][index]),
            }
            for index, name in enumerate(class_order)
        }
        diagnosis_metrics["accuracy"] = float(
            accuracy_score(diagnosis_y, diagnosis_predictions)
        )
        diagnosis_metrics["confusion_matrix_labels_battery_thermal"] = (
            confusion_matrix(
                diagnosis_y, diagnosis_predictions, labels=class_order
            ).tolist()
        )
    else:
        diagnosis_metrics = None

    event_metrics = evaluate_events(
        rows, probabilities, prediction_rows=risk_rows
    )
    failure_types = Counter(
        row.get("failure_type", "none")
        for row in rows if row.get("failure_event", False)
    )
    return {
        "robots": len({row["robot_id"] for row in rows}),
        "valid_records": len(horizon_valid_rows),
        "prediction_ready_valid_records": len(risk_rows),
        "censored_records": sum(
            not row.get("horizon_valid", False) for row in rows
        ),
        "failure_events": sum(failure_types.values()),
        "failure_type_distribution": dict(failure_types),
        "risk": risk_metrics,
        "failure_events_evaluation": event_metrics,
        "diagnosis": diagnosis_metrics,
    }


def run_validation():
    training_rows = build_seed_dataset(TRAINING_SEEDS, "TRAIN")
    trainer = ReliabilityModel(training_rows)
    risk_model, diagnosis_model = trainer.fit_for_validation()
    feature_order = list(risk_model.feature_names_in_)
    if feature_order != list(DEPLOYABLE_FEATURES):
        raise AssertionError("Trained risk model schema changed from the contract")

    training_robot_ids = set(trainer.validation_risk_training_robot_ids)
    results = {}
    for scenario_name, scenario in SCENARIOS.items():
        test_rows = build_seed_dataset(
            scenario["test_seeds"],
            scenario_name,
            scenario["config"],
        )
        test_robot_ids = {row["robot_id"] for row in test_rows}
        if training_robot_ids & test_robot_ids:
            raise AssertionError("Training and evaluation robot IDs overlap")
        if list(risk_model.feature_names_in_) != feature_order:
            raise AssertionError("Feature schema changed across scenarios")
        metrics = evaluate_dataset(risk_model, diagnosis_model, test_rows)
        effective_parameters = dict(DEFAULT_SIMULATION_CONFIG)
        effective_parameters.update(scenario["config"])
        results[scenario_name] = {
            "scenario_parameters": effective_parameters,
            "scenario_parameter_overrides": scenario["config"],
            "workload_scenario": scenario["workload_scenario"],
            "training_seeds": list(TRAINING_SEEDS),
            "test_seeds": list(scenario["test_seeds"]),
            "training_robots": len(training_robot_ids),
            "test_robot_ids_disjoint_from_training": True,
            **metrics,
        }

    baseline = results["BASELINE"]
    drops = []
    for name, result in results.items():
        if name == "BASELINE":
            continue
        drops.extend([
            ("risk F1", name, baseline["risk"]["f1"] - result["risk"]["f1"]),
            ("risk ROC-AUC", name,
             (baseline["risk"]["roc_auc"] or 0)
             - (result["risk"]["roc_auc"] or 0)),
            ("event warning coverage", name,
             baseline["failure_events_evaluation"]["warning_coverage"]
             - result["failure_events_evaluation"]["warning_coverage"]),
        ])
    largest_drop = max(drops, key=lambda entry: entry[2])
    summary = {
        "training": {
            "seeds": list(TRAINING_SEEDS),
            "robots": len(training_robot_ids),
            "records": len(training_rows),
            "simulator_parameters": dict(DEFAULT_SIMULATION_CONFIG),
            "risk_feature_schema": feature_order,
            "diagnosis_feature_schema": list(diagnosis_model.feature_names_in_),
            "censored_records_excluded_from_fit": sum(
                not row.get("horizon_valid", False) for row in training_rows
            ),
        },
        "thresholds": {
            "warning_probability": WARNING_THRESHOLD,
            "warning_consecutive_steps": WARNING_STEPS,
        },
        "scenarios": results,
        "largest_baseline_drop": {
            "metric": largest_drop[0],
            "scenario": largest_drop[1],
            "absolute_drop": float(largest_drop[2]),
        },
        "interpretation": (
            "Simulator results measure sensitivity to these generated shifts; "
            "they do not prove real-world performance."
        ),
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    run_validation()
