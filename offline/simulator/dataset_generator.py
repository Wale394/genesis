import csv
import os
import random

from fleet_simulator import FleetSimulator


class DatasetGenerator:

    def __init__(
        self,
        number_of_robots=100,
        time_steps=80,
        output_path="data/raw_dataset_v2.csv",
        scenario_name="default",
        seed=None,
        simulator_config=None,
    ):
        self.number_of_robots = number_of_robots
        self.time_steps = time_steps
        self.output_path = output_path
        self.scenario_name = scenario_name
        self.seed = seed
        self.simulator_config = dict(simulator_config or {})

    def generate(self):

        if self.seed is not None:
            random.seed(self.seed)

        simulator = FleetSimulator(
            number_of_robots=self.number_of_robots,
            config=self.simulator_config,
        )

        fleet = simulator.create_fleet()

        dataset = []

        for robot in fleet:

            temperature_series = (
                simulator.simulate_temperature_series(
                    robot,
                    time_steps=self.time_steps
                )
            )

            for record in temperature_series:

                                dataset.append({

                    # ========================================
                    # ROBOT IDENTITY
                    # ========================================

                    "robot_id":
                        (
                            f"{self.scenario_name}-seed{self.seed}-"
                            f"{record['robot_id']}"
                            if self.seed is not None
                            else record["robot_id"]
                        ),

                    "manufacturer":
                        robot["manufacturer"],

                    "robot_type":
                        robot["robot_type"],

                    # ========================================
                    # TIME
                    # ========================================

                    "time_step":
                        record["time_step"],

                    # ========================================
                    # THERMAL TELEMETRY
                    # ========================================

                    "motor_temperature":
                        record["motor_temperature"],

                    "ambient_temperature":
                        record["ambient_temperature"],

                    "degradation_level":
                        record["degradation_level"],

                    # ========================================
                    # OPERATING CONDITIONS
                    # ========================================

                    "workload":
                        record["workload"],

                    "robot_state":
                        record["robot_state"],

                    # ========================================
                    # BATTERY TELEMETRY
                    # ========================================

                    "battery_level":
                        record["battery_level"],

                    "battery_health":
                        record["battery_health"],

                    "battery_stress":
                        record["battery_stress"],

                    "battery_voltage":
                        record["battery_voltage"],

                    "battery_current":
                        record["battery_current"],

                    "battery_temperature":
                        record["battery_temperature"],

                    "power_consumption":
                        record["power_consumption"],

                    "voltage_drop":
                        record["voltage_drop"],

                    # ========================================
                    # GROUND TRUTH
                    # ========================================

                    "health":
                        record["health"],

                    "failure_type":
                        record["failure_type"],

                    "failure_event":
                        record["failure_event"],

                    "recovery_event":
                        record["recovery_event"],
                })

        self.save_dataset(dataset)

        return dataset

    def save_dataset(self, dataset):

        if self.output_path is None:
            return

        directory = os.path.dirname(
            self.output_path
        )

        if directory:

            os.makedirs(
                directory,
                exist_ok=True
            )

        if not dataset:
            return

        fieldnames = dataset[0].keys()

        with open(
            self.output_path,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )

            writer.writeheader()

            writer.writerows(dataset)

        print(
            f"\nRaw dataset saved to: "
            f"{self.output_path}"
        )

        print(
            f"Records saved: "
            f"{len(dataset)}"
        )
