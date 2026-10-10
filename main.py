import csv
import os
import random

from telemetry import Telemetry
from history import History
from normalizer import Normalizer
from analyzer import Analyzer
from robot_profile import RobotProfile
from reliability_event import ReliabilityEvent
from pattern_detector import PatternDetector
from risk_engine import RiskEngine

from fleet_simulator import FleetSimulator
from dataset_generator import DatasetGenerator
from label_generator import LabelGenerator
from feature_engineering import FeatureEngineer
from train_model import ReliabilityModel

from prediction_engine import PredictionEngine
from warning_engine import WarningEngine
from diagnosis_engine import DiagnosisEngine
from recommendation_engine import RecommendationEngine
from decision_pipeline import DecisionPipeline
from reliability_state import ReliabilityState
from evidence_engine import EvidenceEngine
from comparison_engine import ComparisonEngine
from baseline_engine import BaselineEngine
from incident_manager import IncidentManager

from data_availability import DataAvailability
from robot_adapter import SimulatedRobotAdapter
from telemetry_features import TelemetryFeatureBuilder
from feature_contract import DEPLOYABLE_FEATURES


# ============================================================
# CONFIGURATION
# ============================================================

random.seed(42)

GENERATE_NEW_DATASET = True

SHOW_DATASET_PREVIEW = False
SHOW_HORIZON_DETAILS = False
INSPECT_ROBOT = "R013"

RAW_DATASET_PATH = "data/raw_dataset.csv"
LABELED_DATASET_PATH = "data/labeled_dataset.csv"
FEATURE_DATASET_PATH = "data/feature_dataset.csv"


# ============================================================
# DATASET HELPERS
# ============================================================


def save_dataset(dataset, output_path):
    if not dataset:
        return

    directory = os.path.dirname(output_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=dataset[0].keys())
        writer.writeheader()
        writer.writerows(dataset)


def load_dataset(input_path):
    numerical_fields = [
        "time_step", "motor_temperature", "ambient_temperature",
        "battery_level", "thermal_rise", "temperature_change",
        "temperature_rate_3", "temperature_rate_5",
        "temperature_avg_3", "temperature_avg_5",
        "thermal_rise_rate_3", "battery_change", "battery_drop_rate_3",
        "battery_voltage", "battery_current", "battery_temperature",
        "power_consumption", "voltage_drop", "battery_voltage_change",
        "battery_voltage_drop_rate_3", "battery_current_change",
        "battery_temperature_change", "battery_temperature_rate_3",
        "power_change", "power_rate_3", "thermal_rise_max_3",
        "thermal_rise_max_5", "thermal_rise_avg_3", "thermal_rise_avg_5",
        "battery_decline_3", "battery_decline_5",
        "thermal_elevated_persistence", "temperature_acceleration",
        "low_battery_persistence", "battery_voltage_decline_3",
        "battery_current_change_3","workload","battery_health",
        "battery_stress",
        "degradation_level",
    ]

    dataset = []

    with open(input_path, "r", newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            for field in numerical_fields:
                if field not in row or row[field] == "":
                    continue
                row[field] = float(row[field])
                if field == "time_step":
                    row[field] = int(row[field])

            if row.get("label", "") != "":
                row["label"] = int(row["label"])

            dataset.append(row)

    return dataset


# ============================================================
# DATASET + MODEL
# ============================================================


def build_feature_dataset():
    print("\n========================================")
    print("DATASET PIPELINE")
    print("========================================")

    if GENERATE_NEW_DATASET:
        dataset = DatasetGenerator(
            number_of_robots=100,
            time_steps=100,
        ).generate()

        labeled_dataset = LabelGenerator(
            prediction_window=10
        ).create_labels(dataset)

        feature_dataset = FeatureEngineer().create_features(
            labeled_dataset
        )

        # Exclude the same four-observation warm-up used by streaming. The
        # simulator labels remain intact in the labeled dataset.
        feature_dataset = [
            record for record in feature_dataset
            if all(record.get(name) is not None for name in DEPLOYABLE_FEATURES)
        ]

        save_dataset(labeled_dataset, LABELED_DATASET_PATH)
        save_dataset(feature_dataset, FEATURE_DATASET_PATH)
    else:
        dataset = load_dataset(RAW_DATASET_PATH)
        labeled_dataset = load_dataset(LABELED_DATASET_PATH)
        # Rebuild loaded features with the current shared contract instead of
        # trusting a previously saved feature file from an older schema.
        feature_dataset = FeatureEngineer().create_features(labeled_dataset)
        feature_dataset = [
            record for record in feature_dataset
            if all(record.get(name) is not None for name in DEPLOYABLE_FEATURES)
        ]

    # Keep categorical model inputs type-consistent.
    # This prevents scikit-learn's OneHotEncoder from receiving
    # a mixture of strings, numbers, and missing values.
    for record in feature_dataset:
        manufacturer = record.get("manufacturer")
        robot_type = record.get("robot_type")

        record["manufacturer"] = (
            "unknown"
            if manufacturer is None or manufacturer == ""
            else str(manufacturer)
        )

        record["robot_type"] = (
            "unknown"
            if robot_type is None or robot_type == ""
            else str(robot_type)
        )

    print(f"Raw records: {len(dataset)}")
    print(f"Labeled records: {len(labeled_dataset)}")
    print(f"Feature records: {len(feature_dataset)}")

    if SHOW_DATASET_PREVIEW:
        print("\nFirst feature record:")
        print(feature_dataset[0])

    return dataset, feature_dataset


def train_model(feature_dataset):
    print("\n========================================")
    print("MODEL TRAINING")
    print("========================================")

    model = ReliabilityModel(feature_dataset)
    model.train()

    prediction_engine = PredictionEngine(model.model)
    diagnosis_engine = DiagnosisEngine(model.diagnosis_model)

    return model, prediction_engine, diagnosis_engine


# ============================================================
# ROBOT INGESTION / MODEL AVAILABILITY
# ============================================================


def print_model_schema(prediction_engine):
    required_features = prediction_engine.get_required_features()

    print("\n========================================")
    print("MODEL REQUIRED FEATURES")
    print("========================================")

    for feature in required_features:
        print("-", feature)


def build_simulated_robot_records():
    return [
        {
            "id": "R001",
            "manufacturer": "Genesis Robotics",
            "robotType": "AMR",
            "motorTemperature": 42.5,
            "temperatureUnit": "C",
            "batteryPercentage": 85.0,
            "batteryVoltage": 48.2,
            "batteryCurrent": 12.5,
            "batteryTemperature": 31.0,
            "powerConsumption": 602.5,
            "voltageDrop": 0.8,
            "workload": 55,
            "ambientTemperature": 28.0,
            "ambientTemperatureUnit": "C",
            "status": "active",
        },
        {
            "id": "R001",
            "manufacturer": "Genesis Robotics",
            "robotType": "AMR",
            "motorTemperature": 45.2,
            "temperatureUnit": "C",
            "batteryPercentage": 83.5,
            "batteryVoltage": 47.9,
            "batteryCurrent": 14.0,
            "batteryTemperature": 31.5,
            "powerConsumption": 670.6,
            "voltageDrop": 1.1,
            "workload": 68,
            "ambientTemperature": 28.0,
            "ambientTemperatureUnit": "C",
            "status": "active",
        },
        {
            "id": "R001",
            "manufacturer": "Genesis Robotics",
            "robotType": "AMR",
            "motorTemperature": 48.7,
            "temperatureUnit": "C",
            "batteryPercentage": 82.0,
            "batteryVoltage": 47.5,
            "batteryCurrent": 16.2,
            "batteryTemperature": 32.2,
            "powerConsumption": 769.5,
            "voltageDrop": 1.5,
            "workload": 82,
            "ambientTemperature": 29.0,
            "ambientTemperatureUnit": "C",
            "status": "active",
        },
    ]


def run_robot_ingestion_test(prediction_engine):
    print("\n========================================")
    print("ROBOT INGESTION + DATA AVAILABILITY")
    print("========================================")

    adapter = SimulatedRobotAdapter(
        build_simulated_robot_records()
    )
    normalizer = Normalizer()
    feature_builder = TelemetryFeatureBuilder()
    data_availability = DataAvailability()

    latest_feature_record = None
    time_step = 0

    while True:
        raw_telemetry = adapter.get_telemetry()
        if raw_telemetry is None:
            break

        time_step += 1

        normalized = normalizer.normalize(raw_telemetry)

        # Keep incoming categorical values consistent with training.
        normalized["manufacturer"] = (
            "unknown"
            if normalized.get("manufacturer") in (None, "")
            else str(normalized["manufacturer"])
        )

        normalized["robot_type"] = (
            "unknown"
            if normalized.get("robot_type") in (None, "")
            else str(normalized["robot_type"])
        )

        snapshot = Telemetry(normalized).snapshot(time_step)
        latest_feature_record = feature_builder.build(snapshot)

        availability = data_availability.can_run_prediction(
            latest_feature_record,
            prediction_engine.model,
        )

        print(f"\n--- TIME STEP {time_step} ---")
        print("Can predict:", availability["can_predict"])

        if availability["missing_features"]:
            print("Missing features:")
            for feature in availability["missing_features"]:
                print("-", feature)
        else:
            print("Missing features: none")

        if availability["missing_categories"]:
            print("Missing categories:")
            for category in availability["missing_categories"]:
                print("-", category)
        else:
            print("Missing categories: none")

    return latest_feature_record


def run_incoming_prediction_test(prediction_engine, feature_record):
    print("\n========================================")
    print("INCOMING ROBOT PREDICTION")
    print("========================================")

    availability = DataAvailability().can_run_prediction(
        feature_record,
        prediction_engine.model,
    )

    if not availability["can_predict"]:
        print("Prediction blocked because required data is missing.")
        return None

    result = prediction_engine.predict(feature_record)

    print("Prediction:", result["prediction"])
    print(
        f"Failure probability: {result['probability']:.2f}"
    )

    return result


# ============================================================
# DECISION PIPELINE
# ============================================================


def build_decision_pipeline(prediction_engine, diagnosis_engine):
    history = History()
    incident_manager = IncidentManager(history)

    pipeline = DecisionPipeline(
        prediction_engine,
        diagnosis_engine,
        RecommendationEngine(),
        ReliabilityState(),
        incident_manager,
        EvidenceEngine(),
        ComparisonEngine(history_window=10),
        BaselineEngine(minimum_records=10),
    )

    return pipeline


def run_decision_tests(pipeline, feature_dataset):
    positive = [
        record for record in feature_dataset
        if record.get("label") == 1 and record.get("time_step", 0) >= 11
    ]
    negative = [
        record for record in feature_dataset
        if record.get("label") == 0 and record.get("time_step", 0) >= 11
    ]

    if not positive or not negative:
        raise RuntimeError("Could not find both positive and negative test cases.")

    def evaluate_case(record, name):
        historical = [
            item for item in feature_dataset
            if (
                item["robot_id"] == record["robot_id"]
                and item["time_step"] < record["time_step"]
            )
        ]
        historical.sort(key=lambda item: item["time_step"])

        print("\n========================================")
        print(f"GENESIS DECISION TEST: {name}")
        print("========================================")
        print("Robot:", record["robot_id"])
        print("Time step:", record["time_step"])
        print("Expected label:", record.get("label"))
        print("Expected failure type:", record.get("failure_type_label"))

        result = pipeline.evaluate(
            record,
            historical_records=historical,
        )

        print("\nRisk:", result["risk"])
        print("Reliability state:", result["state"])
        print("Diagnosis:", result["diagnosis"])
        print("Recommendation:", result["recommendation"])
        print("Actual failure:", result["actual_failure"])

        return result

    evaluate_case(
        positive[len(positive) // 2],
        "POSITIVE — UPCOMING FAILURE",
    )
    evaluate_case(
        negative[len(negative) // 2],
        "NEGATIVE — NO UPCOMING FAILURE",
    )


# ============================================================
# EVIDENCE REPLAY
# ============================================================


def run_evidence_replay(pipeline, feature_dataset):
    robot_records = [
        record.copy()
        for record in feature_dataset
        if record["robot_id"] == INSPECT_ROBOT
    ]
    robot_records.sort(key=lambda record: record["time_step"])

    if not robot_records:
        raise RuntimeError(f"No records found for {INSPECT_ROBOT}.")

    last = robot_records[-1].copy()

    recovery = last.copy()
    recovery["time_step"] = last["time_step"] + 1
    recovery["recovery_event"] = True
    recovery["failure_event"] = False
    recovery["failure_type"] = "none"
    recovery["robot_state"] = "working"
    recovery["motor_temperature"] = 40.0
    recovery["ambient_temperature"] = 25.0
    recovery["thermal_rise"] = 15.0

    stable = recovery.copy()
    stable["time_step"] = recovery["time_step"] + 1
    stable["recovery_event"] = False

    robot_records.extend([recovery, stable])

    print("\n========================================")
    print("GENESIS EVIDENCE REPLAY")
    print("========================================")

    results = pipeline.evaluate_timeline(robot_records)

    for result in results:
        if 47 <= result["time_step"] <= 53:
            print(f"\n--- TIME STEP {result['time_step']} ---")
            for event in result["timeline"]["events"]:
                print(
                    f"t={event['time_step']} | "
                    f"{event['event_type']} | "
                    f"{event['description']}"
                )

    return results


# ============================================================
# FLEET EVALUATION
# ============================================================


def build_test_set(model, feature_dataset):
    return [
        feature_dataset[index]
        for index in model.model1_test_index
    ]


def build_failure_times(records):
    failure_times = {}
    for record in records:
        if record.get("failure_event", False):
            failure_times.setdefault(
                record["robot_id"],
                record["time_step"],
            )
    return failure_times


def evaluate_record_level(prediction_engine, records):
    predictions = prediction_engine.predict_batch(records)
    tp = fp = tn = fn = 0

    for record, prediction in zip(records, predictions):
        actual = record["label"]
        predicted = prediction["prediction"]

        if actual == 1 and predicted == 1:
            tp += 1
        elif actual == 0 and predicted == 1:
            fp += 1
        elif actual == 0 and predicted == 0:
            tn += 1
        else:
            fn += 1

    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0

    print("\n========================================")
    print("HELD-OUT RECORD EVALUATION")
    print("========================================")
    print("Test records:", len(records))
    print("TP:", tp, "FP:", fp, "TN:", tn, "FN:", fn)
    print(f"Precision: {precision:.2%}")
    print(f"Recall: {recall:.2%}")
    print(f"F1: {f1:.2%}")

    # ========================================
    # PROBABILITY THRESHOLD EXPERIMENT
    # ========================================

    print("\n========================================")
    print("PROBABILITY THRESHOLD EXPERIMENT")
    print("========================================")

    test_predictions = predictions
    threshold_results = []

    for threshold in [
        0.10,
        0.15,
        0.20,
        0.25,
        0.30,
        0.35,
        0.40,
        0.45,
        0.50,
        0.55,
        0.60,
        0.65,
        0.70,
        0.75,
        0.80,
        0.85,
        0.90
    ]:

        tp = 0
        fp = 0
        tn = 0
        fn = 0

        for record, prediction in zip(
            records,
            test_predictions
        ):

            actual = int(record["label"])
            probability = prediction["probability"]

            predicted = (
                1
                if probability >= threshold
                else 0
            )

            if actual == 1 and predicted == 1:
                tp += 1
            elif actual == 0 and predicted == 1:
                fp += 1
            elif actual == 0 and predicted == 0:
                tn += 1
            elif actual == 1 and predicted == 0:
                fn += 1

        precision = (
            tp / (tp + fp)
            if (tp + fp) > 0
            else 0
        )

        recall = (
            tp / (tp + fn)
            if (tp + fn) > 0
            else 0
        )

        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0
        )

        threshold_results.append({
            "threshold": threshold,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn
        })

    print(
        "Threshold | Precision | Recall | F1 | TP | FP | FN"
    )
    print(
        "---------------------------------------------------"
    )

    for result in threshold_results:

        print(
            f"{result['threshold']:.2f}       | "
            f"{result['precision'] * 100:8.2f}% | "
            f"{result['recall'] * 100:6.2f}% | "
            f"{result['f1'] * 100:5.2f}% | "
            f"{result['tp']:2d} | "
            f"{result['fp']:2d} | "
            f"{result['fn']:2d}"
        )


def build_prediction_timelines(prediction_engine, records):
    predictions = prediction_engine.predict_batch(records)
    timelines = {}

    for record, prediction in zip(records, predictions):
        robot_id = record["robot_id"]
        timelines.setdefault(robot_id, []).append({
            "time_step": record["time_step"],
            "probability": prediction["probability"],
            "prediction": prediction["prediction"],
            "actual_label": record.get("label", 0),
            "failure_event": record.get("failure_event", False),
            "failure_type": record.get("failure_type", "none"),
            "battery_level": record.get("battery_level"),
            "battery_voltage": record.get("battery_voltage"),
            "motor_temperature": record.get("motor_temperature"),
            "thermal_rise": record.get("thermal_rise"),
        })

    for timeline in timelines.values():
        timeline.sort(key=lambda point: point["time_step"])

    return timelines


def run_warning_experiments(predictions_by_robot):
    configurations = [
        (0.30, 2), (0.30, 3), (0.30, 4),
        (0.40, 2), (0.40, 3), (0.40, 4),
    ]

    print("\n========================================")
    print("WARNING ENGINE EXPERIMENT")
    print("========================================")
    print("Threshold | Steps | Precision | Recall | Warnings | Early | Avg Lead")
    print("-" * 75)

    for threshold, steps in configurations:
        engine = WarningEngine(
            probability_threshold=threshold,
            consecutive_steps=steps,
        )

        tp = fp = fn = 0
        lead_times = []

        for timeline in predictions_by_robot.values():
            failure_time = next(
                (
                    point["time_step"]
                    for point in timeline
                    if point["failure_event"]
                ),
                None,
            )

            warning_time = engine.evaluate_robot(timeline)["warning_time"]

            if failure_time is not None:
                if warning_time is not None and warning_time < failure_time:
                    tp += 1
                    lead_times.append(failure_time - warning_time)
                else:
                    fn += 1
            elif warning_time is not None:
                fp += 1

        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn) if tp + fn else 0
        average_lead = sum(lead_times) / len(lead_times) if lead_times else 0

        print(
            f"{threshold:.2f}       | {steps}     | "
            f"{precision:.2%}   | {recall:.2%} | "
            f"{tp + fp:8} | {len(lead_times):5} | {average_lead:.2f}"
        )


def run_horizon_analysis(predictions_by_robot, failure_times):
    threshold = 0.30
    lead_times = []

    for robot_id, timeline in predictions_by_robot.items():
        if robot_id not in failure_times:
            continue

        failure_time = failure_times[robot_id]
        warning_time = next(
            (
                point["time_step"]
                for point in timeline
                if (
                    point["time_step"] < failure_time
                    and point["probability"] >= threshold
                )
            ),
            None,
        )

        if warning_time is not None:
            lead_times.append(failure_time - warning_time)
            if SHOW_HORIZON_DETAILS:
                print(
                    f"{robot_id}: failure={failure_time}, "
                    f"warning={warning_time}, "
                    f"lead={failure_time - warning_time}"
                )
        elif SHOW_HORIZON_DETAILS:
            print(f"{robot_id}: NO EARLY WARNING (failure={failure_time})")

    total = len(failure_times)
    successful = len(lead_times)

    print("\n========================================")
    print("WARNING HORIZON SUMMARY")
    print("========================================")
    print("Total failures:", total)
    print("Successful early warnings:", successful)
    print("Missed failures:", total - successful)
    print(f"Warning coverage: {successful / total:.2%}" if total else "Warning coverage: 0.00%")
    print(
        f"Average lead time: {sum(lead_times) / successful:.2f} steps"
        if successful else "Average lead time: 0.00 steps"
    )
    print(f"Minimum lead time: {min(lead_times)} steps" if lead_times else "Minimum lead time: 0 steps")
    print(f"Maximum lead time: {max(lead_times)} steps" if lead_times else "Maximum lead time: 0 steps")


# ============================================================
# OPTIONAL LEGACY ANALYZER DEMO
# ============================================================


def run_legacy_rule_demo():
    """Keep the original rule-based layer available without mixing it into main."""

    history = History()
    normalizer = Normalizer()
    profile = RobotProfile(
        robot_id="X501",
        normal_working_temperature=45,
        abnormal_working_temperature=50,
        critical_working_temperature=60,
        normal_idle_temperature=35,
        abnormal_idle_temperature=40,
        critical_idle_temperature=50,
        normal_ambient_temperature=22,
        abnormal_ambient_temperature=30,
        critical_ambient_temperature=40,
        normal_thermal_rise=10,
        abnormal_thermal_rise=20,
        critical_thermal_rise=35,
    )

    temperatures = [30, 55, 80, 105, 100, 95, 60]
    ambients = [20, 30, 40, 50, 45, 40, 45]

    for step, (temperature, ambient) in enumerate(
        zip(temperatures, ambients),
        start=1,
    ):
        normalized = normalizer.normalize({
            "robot_id": "X501",
            "motor_temp": temperature,
            "temp_unit": "C",
            "battery": 85,
            "state": "active",
            "ambient_temp": ambient,
            "ambient_temp_unit": "C",
        })
        history.store(
            Telemetry(normalized).snapshot(step)
        )

    analyzer = Analyzer(history)
    analyzer.check_temperature()
    analyzer.check_temperature_trend()
    analyzer.check_temperature_change()
    analyzer.check_temperature_context(profile)
    analyzer.check_ambient_temperature(profile)
    analyzer.check_thermal_rise()
    analyzer.check_relative_thermal_change()
    analyzer.analyze_thermal_behavior(profile)



def analyze_failure_probability_timelines(
    prediction_engine,
    records,
    lookback=15
):
    print("\n========================================")
    print("FAILURE PROBABILITY TIMELINES")
    print("========================================")

    # Group records by robot
    robots = {}

    for record in records:
        robot_id = record["robot_id"]

        if robot_id not in robots:
            robots[robot_id] = []

        robots[robot_id].append(record)

    # Make sure each robot's records are ordered
    for robot_records in robots.values():
        robot_records.sort(
            key=lambda record: record["time_step"]
        )

    failures_found = 0

    for robot_id, robot_records in robots.items():

        # Find actual failure events
        failure_indices = [
            index
            for index, record in enumerate(robot_records)
            if record.get("failure_event", False)
        ]

        for failure_index in failure_indices:

            failure_record = robot_records[failure_index]

            failure_step = failure_record["time_step"]
            failure_type = failure_record.get(
                "failure_type",
                "unknown"
            )

            start_index = max(
                0,
                failure_index - lookback
            )

            timeline_records = robot_records[
                start_index:failure_index + 1
            ]

            predictions = prediction_engine.predict_batch(
                timeline_records
            )

            print("\n----------------------------------------")
            print(f"Robot: {robot_id}")
            print(f"Failure type: {failure_type}")
            print(f"Failure step: {failure_step}")
            print("----------------------------------------")

            print(
                f"{'Step':<8}"
                f"{'Probability':<15}"
                f"{'Prediction':<12}"
                f"{'Actual':<10}"
            )

            for record, prediction in zip(
                timeline_records,
                predictions
            ):
                step = record["time_step"]
                probability = prediction["probability"]
                predicted_failure = prediction["prediction"]
                actual_failure = record.get(
                    "failure_event",
                    False
                )

                print(
                    f"{step:<8}"
                    f"{probability:<15.4f}"
                    f"{predicted_failure:<12}"
                    f"{str(actual_failure):<10}"
                )

            # Find first threshold crossings
            print("\nThreshold crossings:")

            for threshold in [
                0.20,
                0.30,
                0.40,
                0.50,
                0.60,
                0.70
            ]:
                crossing_step = None

                for record, prediction in zip(
                    timeline_records,
                    predictions
                ):
                    if prediction["probability"] >= threshold:
                        crossing_step = record["time_step"]
                        break

                if crossing_step is not None:
                    lead_time = failure_step - crossing_step

                    print(
                        f"  {threshold:.2f}"
                        f" → step {crossing_step}"
                        f" → lead {lead_time} steps"
                    )
                else:
                    print(
                        f"  {threshold:.2f}"
                        f" → not crossed"
                    )

            failures_found += 1

    print("\n========================================")
    print("TIMELINE ANALYSIS COMPLETE")
    print("========================================")
    print(f"Failures analyzed: {failures_found}")



def analyze_failure_signals(
    prediction_engine,
    records,
    lookback=15
):
    print("\n========================================")
    print("FAILURE SIGNAL ANALYSIS")
    print("========================================")

    robots = {}

    for record in records:
        robot_id = record["robot_id"]

        if robot_id not in robots:
            robots[robot_id] = []

        robots[robot_id].append(record)

    for robot_records in robots.values():
        robot_records.sort(
            key=lambda record: record["time_step"]
        )

    failures_found = 0

    for robot_id, robot_records in robots.items():

        failure_indices = [
            index
            for index, record in enumerate(robot_records)
            if record.get("failure_event", False)
        ]

        for failure_index in failure_indices:

            failure_record = robot_records[failure_index]

            failure_step = failure_record["time_step"]
            failure_type = failure_record.get(
                "failure_type",
                "unknown"
            )

            start_index = max(
                0,
                failure_index - lookback
            )

            timeline_records = robot_records[
                start_index:failure_index + 1
            ]

            predictions = prediction_engine.predict_batch(
                timeline_records
            )

            print("\n----------------------------------------")
            print(f"Robot: {robot_id}")
            print(f"Failure type: {failure_type}")
            print(f"Failure step: {failure_step}")
            print("----------------------------------------")

            print(
                f"{'Step':<7}"
                f"{'Risk':<8}"
                f"{'Motor°C':<10}"
                f"{'Thermal':<10}"
                f"{'Battery%':<10}"
                f"{'Voltage':<10}"
                f"{'Current':<10}"
                f"{'Workload':<10}"
            )

            for record, prediction in zip(
                timeline_records,
                predictions
            ):
                print(
                    f"{record['time_step']:<7}"
                    f"{prediction['probability']:<8.2f}"
                    f"{record['motor_temperature']:<10.2f}"
                    f"{record['thermal_rise']:<10.2f}"
                    f"{record['battery_level']:<10.2f}"
                    f"{record['battery_voltage']:<10.2f}"
                    f"{record['battery_current']:<10.2f}"
                    f"{record['workload']:<10.2f}"
                )

            failures_found += 1

    print("\n========================================")
    print("FAILURE SIGNAL ANALYSIS COMPLETE")
    print("========================================")
    print(f"Failures analyzed: {failures_found}")
# ============================================================
# MAIN
# ============================================================


def main():
    print("\n========================================")
    print("GENESIS LAB")
    print("========================================")

    # 1. Build the training feature dataset.
    _, feature_dataset = build_feature_dataset()

    # 2. Train the reliability model.
    model, prediction_engine, diagnosis_engine = train_model(
        feature_dataset
    )

    # 3. Let the trained model define the authoritative input schema.
    print_model_schema(prediction_engine)

    # 4. Simulate the real robot ingestion boundary.
    latest_feature_record = run_robot_ingestion_test(
        prediction_engine
    )

    # 5. Run the actual trained model on incoming robot data.
    run_incoming_prediction_test(
        prediction_engine,
        latest_feature_record,
    )

    # 6. Build Genesis' decision layer.
    pipeline = build_decision_pipeline(
        prediction_engine,
        diagnosis_engine,
    )

    # 7. Test positive/negative decision cases.
    run_decision_tests(
        pipeline,
        feature_dataset,
    )

    # 8. Replay a failure/recovery timeline.
    run_evidence_replay(
        pipeline,
        feature_dataset,
    )

    # 9. Evaluate on held-out robots.
    test_records = build_test_set(
        model,
        feature_dataset,
    )

    evaluate_record_level(
        prediction_engine,
        test_records,
    )

    prediction_timelines = build_prediction_timelines(
        prediction_engine,
        test_records,
    )

    analyze_failure_probability_timelines(
        prediction_engine,
        test_records,
        lookback=15,
    )

    analyze_failure_signals(
        prediction_engine,
        test_records,
        lookback=15,
    )

    failure_times = build_failure_times(
        test_records,
    )

    # 10. Evaluate operational warnings.
    run_warning_experiments(
        prediction_timelines,
    )

    run_horizon_analysis(
        prediction_timelines,
        failure_times,
    )

    print("\n========================================")
    print("GENESIS RUN COMPLETE")
    print("========================================")


if __name__ == "__main__":
    main()

