import random

from dataset_generator import DatasetGenerator
from label_generator import LabelGenerator
from feature_engineering import FeatureEngineer
from train_model import ReliabilityModel
from prediction_engine import PredictionEngine
from reliability_signal import ReliabilitySignal


SEED = 42

NUMBER_OF_ROBOTS = 100
TIME_STEPS = 100
PREDICTION_WINDOW = 10


def build_dataset():

    random.seed(SEED)

    dataset = DatasetGenerator(
        number_of_robots=NUMBER_OF_ROBOTS,
        time_steps=TIME_STEPS,
        output_path="data/false_warning_inspection.csv"
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
    print("INSPECTING FIRST HYBRID FALSE WARNING")
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

    signal_engine = ReliabilitySignal()

    records_by_robot = {}

    for record, prediction in zip(
        test_records,
        predictions
    ):

        robot_id = record["robot_id"]

        records_by_robot.setdefault(
            robot_id,
            []
        ).append({
            "record": record,
            "prediction": prediction
        })

    # --------------------------------------------------------
    # Find first robot with engineering warning but
    # no actual failure.
    # --------------------------------------------------------

    false_warning = None

    for robot_id, timeline in records_by_robot.items():

        timeline.sort(
            key=lambda item:
            item["record"]["time_step"]
        )

        for item in timeline:

            record = item["record"]

            signal_result = signal_engine.analyze(
                record
            )

            if (
                signal_result["severity"] == "critical"
                and not record.get(
                    "failure_event",
                    False
                )
            ):

                false_warning = {
                    "robot_id": robot_id,
                    "timeline": timeline,
                    "warning_time":
                        record["time_step"]
                }

                break

        if false_warning:
            break

    if false_warning is None:

        print(
            "\nNo false engineering warning found."
        )

        return

    robot_id = false_warning["robot_id"]
    warning_time = false_warning["warning_time"]

    print(
        f"\nFirst false warning: {robot_id}"
    )

    print(
        f"Engineering warning time: "
        f"t={warning_time}"
    )

    print(
        "\nComplete robot timeline:"
    )

    print("-" * 130)

    for item in false_warning["timeline"]:

        record = item["record"]
        prediction = item["prediction"]

        signal_result = signal_engine.analyze(
            record
        )

        signal_names = [
            signal["signal"]
            for signal
            in signal_result["signals"]
        ]

        print(
            f"t={record['time_step']:>3} | "
            f"ML={prediction['probability']:.2f} | "
            f"failure={record.get('failure_event', False)} | "
            f"type={record.get('failure_type', 'none'):<8} | "
            f"battery={record.get('battery_level', 0):>6.2f} | "
            f"battery_health={record.get('battery_health', 0):>6.3f} | "
            f"current={record.get('battery_current', 0):>6.2f} | "
            f"voltage={record.get('battery_voltage', 0):>6.2f} | "
            f"workload={record.get('workload', 0):>6.2f} | "
            f"signals={signal_names}"
        )

    print("\n========================================")
    print("END INSPECTION")
    print("========================================")


if __name__ == "__main__":
    main()