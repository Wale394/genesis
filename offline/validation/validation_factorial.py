"""Isolated 2x2 diagnostic experiment for telemetry noise and coupling.

This runner uses the validation harness's fitted baseline model, test seeds,
feature schema, filtering, warning methodology, and thresholds. It does not
change the simulator, production model, or production thresholds.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from feature_contract import DEPLOYABLE_FEATURES
from fleet_simulator import DEFAULT_SIMULATION_CONFIG
from reliability_signal import ReliabilitySignal
from train_model import ReliabilityModel
from validation_experiment import (
    BASELINE_TEST_SEEDS,
    TRAINING_SEEDS,
    build_seed_dataset,
    evaluate_events,
)


FULL_STRESS = {
    "telemetry_noise_scale": 2.5,
    "thermal_observation_coupling": 4.0,
    "battery_observation_coupling": 0.4,
    "thermal_failure_uses_observed_temperature": False,
}
ARMS = {
    "BASELINE": {},
    "NOISE_ONLY": {"telemetry_noise_scale": 2.5},
    "COUPLING_ONLY": {
        key: value for key, value in FULL_STRESS.items()
        if key != "telemetry_noise_scale"
    },
    "FULL_STRESS": FULL_STRESS,
}
FEATURE_GROUPS = {
    "thermal": tuple(name for name in DEPLOYABLE_FEATURES if any(
        token in name for token in ("temperature", "thermal", "temp_")
    )),
    "battery": tuple(name for name in DEPLOYABLE_FEATURES if any(
        token in name for token in ("battery", "voltage", "current", "low_battery")
    )),
    "workload": tuple(name for name in DEPLOYABLE_FEATURES if any(
        token in name for token in ("workload", "power_consumption")
    )),
}


def _ready_rows(rows):
    return [row for row in rows if row.get("horizon_valid") is True and all(
        row.get(feature) is not None for feature in DEPLOYABLE_FEATURES
    )]


def _risk_metrics(model, rows):
    X = pd.DataFrame(
        [{name: row[name] for name in DEPLOYABLE_FEATURES} for row in rows],
        columns=DEPLOYABLE_FEATURES,
    )
    y = np.asarray([int(row["label"]) for row in rows], dtype=int)
    predicted = np.asarray(model.predict(X), dtype=int)
    positive_index = list(model.classes_).index(1)
    probability = np.asarray(model.predict_proba(X))[:, positive_index]
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    cohorts = {}
    for name, mask in {
        "TP": (y == 1) & (predicted == 1),
        "TN": (y == 0) & (predicted == 0),
        "FP": (y == 0) & (predicted == 1),
        "FN": (y == 1) & (predicted == 0),
    }.items():
        cohorts[name] = {
            "count": int(mask.sum()),
            "mean_probability": float(probability[mask].mean()) if mask.any() else None,
        }
    return {
        "records": len(rows),
        "precision": float(precision_score(y, predicted, zero_division=0)),
        "recall": float(recall_score(y, predicted, zero_division=0)),
        "f1": float(f1_score(y, predicted, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, probability)),
        "pr_auc": float(average_precision_score(y, probability)),
        "brier_score": float(brier_score_loss(y, probability)),
        "confusion_matrix": {"labels": [0, 1], "rows_actual_cols_predicted": [[int(tn), int(fp)], [int(fn), int(tp)]]},
        "probability_cohorts": cohorts,
        "probabilities": probability,
    }


def _engineering_signals(rows):
    signal = ReliabilitySignal()
    positives = [row for row in rows if row.get("label") == 1]
    negatives = [row for row in rows if row.get("label") == 0]

    def summarize(selected):
        outputs = [signal.analyze(row) for row in selected]
        return {
            "any_signal_rate": float(np.mean([bool(item["signals"]) for item in outputs])) if outputs else None,
            "critical_motor_temperature_rate": float(np.mean([
                any(s["signal"] == "critical_motor_temperature" for s in item["signals"])
                for item in outputs
            ])) if outputs else None,
            "critical_thermal_rise_rate": float(np.mean([
                any(s["signal"] == "critical_thermal_rise" for s in item["signals"])
                for item in outputs
            ])) if outputs else None,
            "critical_battery_level_rate": float(np.mean([
                any(s["signal"] == "critical_battery_level" for s in item["signals"])
                for item in outputs
            ])) if outputs else None,
        }

    return {
        "all_records": summarize(rows),
        "positive_label_records": summarize(positives),
        "negative_label_records": summarize(negatives),
    }


def _feature_summary(rows):
    frame = pd.DataFrame([{name: row.get(name) for name in DEPLOYABLE_FEATURES} for row in rows])
    result = {}
    for group, features in FEATURE_GROUPS.items():
        available = [name for name in features if name in frame and pd.api.types.is_numeric_dtype(frame[name])]
        result[group] = {
            "features": available,
            "mean_of_feature_means": float(frame[available].mean().mean()) if available else None,
            "mean_of_feature_stds": float(frame[available].std().mean()) if available else None,
        }
    return result


def run_factorial():
    training_rows = build_seed_dataset(TRAINING_SEEDS, "TRAIN")
    trainer = ReliabilityModel(training_rows)
    risk_model, _ = trainer.fit_for_validation()
    if list(risk_model.feature_names_in_) != list(DEPLOYABLE_FEATURES):
        raise AssertionError("Baseline model feature order differs from the feature contract")

    results = {}
    arm_rows = {}
    baseline_feature_stats = None
    for arm_name, overrides in ARMS.items():
        config = dict(DEFAULT_SIMULATION_CONFIG)
        config.update(overrides)
        rows = build_seed_dataset(BASELINE_TEST_SEEDS, arm_name, config)
        ready = _ready_rows(rows)
        metrics = _risk_metrics(risk_model, ready)
        probabilities = metrics.pop("probabilities")
        feature_stats = _feature_summary(ready)
        if baseline_feature_stats is None:
            baseline_feature_stats = feature_stats
        feature_shifts = {}
        for feature in DEPLOYABLE_FEATURES:
            values = pd.to_numeric(pd.Series([r.get(feature) for r in ready]), errors="coerce")
            base_values = pd.to_numeric(pd.Series([
                r.get(feature) for r in arm_rows.get("BASELINE", [])
                if r.get("horizon_valid") is True and all(r.get(f) is not None for f in DEPLOYABLE_FEATURES)
            ]), errors="coerce")
            feature_shifts[feature] = {
                "mean": float(values.mean()),
                "std": float(values.std()),
                "missing_rate": float(values.isna().mean()),
                "mean_delta_from_baseline": (
                    float(values.mean() - base_values.mean()) if len(base_values) else 0.0
                ),
            }
        event_metrics = evaluate_events(rows, probabilities, prediction_rows=ready)
        results[arm_name] = {
            "parameter_overrides": overrides,
            "test_seeds": list(BASELINE_TEST_SEEDS),
            "robots": len({r["robot_id"] for r in rows}),
            "horizon_valid_records": sum(r.get("horizon_valid") is True for r in rows),
            "prediction_ready_records": len(ready),
            "censored_records": sum(r.get("horizon_valid") is not True for r in rows),
            "risk": metrics,
            "event_warning": event_metrics,
            "engineering_signals": _engineering_signals(ready),
            "feature_groups": feature_stats,
            "feature_behavior": feature_shifts,
        }
        arm_rows[arm_name] = rows

    baseline_f1 = results["BASELINE"]["risk"]["f1"]
    degradation = {
        name.lower(): {
            "f1_absolute_drop": baseline_f1 - results[name]["risk"]["f1"],
            "f1_relative_drop": (baseline_f1 - results[name]["risk"]["f1"]) / baseline_f1 if baseline_f1 else None,
        }
        for name in ("NOISE_ONLY", "COUPLING_ONLY", "FULL_STRESS")
    }
    interaction = (
        results["FULL_STRESS"]["risk"]["f1"]
        - results["NOISE_ONLY"]["risk"]["f1"]
        - results["COUPLING_ONLY"]["risk"]["f1"]
        + baseline_f1
    )
    output = {
        "experiment": "Genesis telemetry stress 2x2 diagnostic factorial",
        "training_seeds": list(TRAINING_SEEDS),
        "test_seeds": list(BASELINE_TEST_SEEDS),
        "training_model_fit_count": 1,
        "thresholds": {"risk_model_internal": "unchanged fitted classifier threshold", "warning_probability": 0.30, "warning_consecutive_steps": 2},
        "workload": "current synchronized workload cycle",
        "feature_contract": list(DEPLOYABLE_FEATURES),
        "arms": results,
        "f1_degradation_from_baseline": degradation,
        "f1_factorial_interaction_full_minus_noise_minus_coupling_plus_baseline": interaction,
        "interpretation_note": "Negative interaction means combined full stress loses additional F1 beyond the sum of single-arm effects; positive means sub-additive loss.",
    }
    out_path = Path("data/telemetry_stress_factorial_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(out_path),
        "training_model_fit_count": 1,
        "arms": {
            name: {
                "risk": arm["risk"],
                "event_warning": arm["event_warning"],
                "engineering_signals": arm["engineering_signals"],
                "records": arm["prediction_ready_records"],
            }
            for name, arm in results.items()
        },
        "f1_degradation_from_baseline": degradation,
        "f1_factorial_interaction": interaction,
    }, indent=2))
    return output


if __name__ == "__main__":
    run_factorial()
