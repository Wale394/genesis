from normalizer import Normalizer
from telemetry import Telemetry
from history import History
from analyzer import Analyzer
from telemetry_features import TelemetryFeatureBuilder


class RobotAdapter:

    def get_telemetry(self):
        raise NotImplementedError(
            "Robot adapters must implement get_telemetry()."
        )


class SimulatedRobotAdapter(RobotAdapter):

    def __init__(self, records):
        self.records = records
        self.index = 0

    def get_telemetry(self):

        if self.index >= len(self.records):
            return None

        record = self.records[self.index]
        self.index += 1

        return record


if __name__ == "__main__":

    simulated_records = [

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

            "status": "active"
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

            "status": "active"
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

            "status": "active"
        }
    ]

    adapter = SimulatedRobotAdapter(
        simulated_records
    )

    normalizer = Normalizer()
    history = History()
    analyzer = Analyzer(history)
    feature_builder = TelemetryFeatureBuilder()

    time_step = 0

    while True:

        raw_telemetry = adapter.get_telemetry()

        if raw_telemetry is None:
            break

        time_step += 1

        normalized = normalizer.normalize(
            raw_telemetry
        )

        telemetry = Telemetry(normalized)

        snapshot = telemetry.snapshot(
            time_step
        )

        feature_record = feature_builder.build(
            snapshot
        )

        print("\nFeature Record:")
        print(feature_record)

        print("\nFeature Availability:")
        print(
            feature_builder.get_available_features(
                feature_record
            )
        )

        history.store(snapshot)

        print("\nTelemetry:")
        print(snapshot)

    print("\n===== GENESIS ANALYSIS =====")

    analyzer.check_temperature()
    analyzer.check_temperature_trend()
    analyzer.check_temperature_change()
    analyzer.check_thermal_rise()
    analyzer.check_relative_thermal_change()