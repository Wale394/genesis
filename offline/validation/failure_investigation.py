import random

from dataset_generator import DatasetGenerator
from label_generator import LabelGenerator
from feature_engineering import FeatureEngineer
from train_model import ReliabilityModel
from prediction_engine import PredictionEngine
from warning_engine import WarningEngine


SEED = 44

NUMBER_OF_ROBOTS = 100
TIME_STEPS = 100

PREDICTION_WINDOW = 10

WARNING_THRESHOLD = 0.30
WARNING_STEPS = 2


def build_dataset():

    random.seed(SEED)

    dataset = DatasetGenerator(
        number_of_robots=NUMBER_OF_ROBOTS,
        time_steps=TIME_STEPS,
        output_path=f"data/investigation_raw_{SEED}.csv"
    ).generate()

    labeled_dataset = LabelGenerator(
        prediction_window=PREDICTION_WINDOW
    ).create_labels(dataset)

    feature_dataset = FeatureEngineer().create_features(
        labeled_dataset
    )

    for record in feature_dataset:

        record["manufacturer"] = str(
            record.get("manufacturer") or "unknown"
        )

        record["robot_type"] = str(
            record.get("robot_type") or "unknown"
        )

    return feature_dataset


def main():

    print("\n========================================")
    print("GENESIS FAILURE INVESTIGATION")
    print(f"SEED: {SEED}")
    print("========================================")

    feature_dataset = build_dataset()

    model = ReliabilityModel(
        feature_dataset
    )

    model.train()

    prediction_engine = PredictionEngine(
        model.model
    )

    test_records = [
        feature_dataset[index]
        for index in model.model1_test_index
    ]

    predictions = prediction_engine.predict_batch(
        test_records
    )

    records_by_robot = {}

    for record, prediction in zip(
        test_records,
        predictions
    ):

        robot_id = record["robot_id"]

        if robot_id not in records_by_robot:
            records_by_robot[robot_id] = []

        records_by_robot[robot_id].append({
            "record": record,
            "prediction": prediction
        })

    warning_engine = WarningEngine(
        probability_threshold=WARNING_THRESHOLD,
        consecutive_steps=WARNING_STEPS
    )

    print("\nSearching for missed failures...\n")

    missed = []

    for robot_id, timeline in records_by_robot.items():

        timeline.sort(
            key=lambda item:
            item["record"]["time_step"]
        )

        failure_records = [
            item
            for item in timeline
            if item["record"].get(
                "failure_event",
                False
            )
        ]

        if not failure_records:
            continue

        failure_time = failure_records[0][
            "record"
        ]["time_step"]

        warning_timeline = [

            {
                "time_step":
                    item["record"]["time_step"],

                "probability":
                    item["prediction"]["probability"],

                "prediction":
                    item["prediction"]["prediction"],

                "failure_event":
                    item["record"].get(
                        "failure_event",
                        False
                    ),

                "failure_type":
                    item["record"].get(
                        "failure_type",
                        "none"
                    )
            }

            for item in timeline
        ]

        warning_result = warning_engine.evaluate_robot(
            warning_timeline
        )

        warning_time = warning_result["warning_time"]

        if (
            warning_time is None
            or warning_time >= failure_time
        ):

            missed.append({
                "robot_id": robot_id,
                "failure_time": failure_time,
                "warning_time": warning_time,
                "failure_type":
                    failure_records[0]["record"].get(
                        "failure_type",
                        "none"
                    ),
                "timeline": timeline
            })

    if not missed:

        print("No missed failures found.")
        return

    print(
        f"Found {len(missed)} missed failure(s).\n"
    )

    for case in missed:

        print("\n========================================")
        print(
            f"MISSED FAILURE — {case['robot_id']}"
        )
        print("========================================")

        print(
            f"Failure type: "
            f"{case['failure_type']}"
        )

        print(
            f"Actual failure time: "
            f"t={case['failure_time']}"
        )

        print(
            f"Warning time: "
            f"{case['warning_time']}"
        )

        print("\nTimeline:")

        for item in case["timeline"]:

            record = item["record"]
            prediction = item["prediction"]

            time_step = record["time_step"]

            probability = prediction[
                "probability"
            ]

            predicted = prediction[
                "prediction"
            ]

            print(
                f"t={time_step:>3} | "
                f"prob={probability:.2f} | "
                f"pred={predicted} | "
                f"failure="
                f"{record.get('failure_event', False)} | "
                f"motor="
                f"{record.get('motor_temperature', 0):.2f} | "
                f"ambient="
                f"{record.get('ambient_temperature', 0):.2f} | "
                f"thermal_rise="
                f"{record.get('thermal_rise', 0):.2f} | "
                f"battery="
                f"{record.get('battery_level', 0):.2f} | "
                f"current="
                f"{record.get('battery_current', 0):.2f} | "
                f"workload="
                f"{record.get('workload', 0):.2f}"
            )

        print("\nAnalysis window:")

        start = max(
            0,
            case["failure_time"] - 15
        )

        for item in case["timeline"]:

            record = item["record"]

            if record["time_step"] < start:
                continue

            print(
                f"t={record['time_step']:>3} "
                f"| probability="
                f"{item['prediction']['probability']:.2f}"
            )


if __name__ == "__main__":
    main()