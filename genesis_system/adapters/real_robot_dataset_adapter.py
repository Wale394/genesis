"""Translate Robot Predictive Maintenance CSV rows into Genesis observations.

This adapter only translates fields. In particular, dataset labels are read
only by the separate ``load_ground_truth`` method and never enter observations.
"""

import argparse
import csv
import math
from pathlib import Path


SOURCE_NAME = "robot_predictive_maintenance_dataset"
REQUIRED_COLUMNS = ("time", "temperature")


class RealRobotDatasetAdapter:
    """Load one motor CSV as canonical ``identity``/``telemetry`` records."""

    def __init__(self, dataset_root, run_id, motor_number):
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        if isinstance(motor_number, bool):
            raise ValueError("motor_number must be a positive integer")
        try:
            motor_number = int(motor_number)
        except (TypeError, ValueError) as exc:
            raise ValueError("motor_number must be a positive integer") from exc
        if motor_number < 1:
            raise ValueError("motor_number must be a positive integer")

        self.dataset_root = Path(dataset_root).expanduser()
        self.run_id = run_id
        self.motor_number = motor_number
        self.motor_id = f"motor_{motor_number}"
        self.path = self._resolve_csv()

    def load_observations(self):
        """Return canonical observations, excluding all ground-truth values."""
        observations = []
        for line_number, columns, row in self._read_rows():
            timestamp_raw = row.get("time")
            timestamp = self._number(timestamp_raw, "time", line_number, required=True)
            temperature_raw = row.get("temperature")
            temperature = self._number(
                temperature_raw, "temperature", line_number, required=False
            )

            original_values = {
                name: row.get(name)
                for name in ("time", "temperature", "position", "voltage")
                if name in columns
            }
            metadata = {
                "source": SOURCE_NAME,
                "run_id": self.run_id,
                "motor_id": self.motor_id,
                "original_file": str(self.path.resolve()),
                "original_columns": list(columns),
                "source_timestamp": timestamp_raw,
                "original_values": original_values,
                "unmapped_fields": {
                    name: row.get(name)
                    for name in ("position", "voltage")
                    if name in columns
                },
                "limitations": [
                    "Dataset voltage is not mapped to battery_voltage because its motor/battery semantics and unit are unspecified.",
                    "Dataset position has no corresponding field in the current Genesis telemetry contract.",
                ],
            }
            observations.append({
                "identity": {
                    "robot_id": f"{self.run_id}_{self.motor_id}",
                    "manufacturer": None,
                    "robot_type": None,
                },
                "telemetry": {
                    "time_step": timestamp,
                    "motor_temperature": temperature,
                },
                "source_metadata": metadata,
            })
        return observations

    def load_ground_truth(self):
        """Return validation-only labels in a separate structure.

        These records are not attached to observations and callers must keep
        them outside the Genesis inference path.
        """
        records = []
        for line_number, columns, row in self._read_rows():
            if "label" not in columns:
                continue
            records.append({
                "run_id": self.run_id,
                "motor_id": self.motor_id,
                "timestamp": row.get("time"),
                "label": row.get("label"),
            })
        return records

    def _read_rows(self):
        try:
            with self.path.open("r", newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                columns = reader.fieldnames or []
                missing = [name for name in REQUIRED_COLUMNS if name not in columns]
                if missing:
                    raise ValueError(
                        f"Malformed dataset CSV {self.path}: missing required column(s): "
                        + ", ".join(missing)
                    )
                for line_number, row in enumerate(reader, start=2):
                    if None in row:
                        raise ValueError(
                            f"Malformed dataset CSV {self.path} at line {line_number}: "
                            "row has more values than the header"
                        )
                    yield line_number, columns, row
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Motor CSV not found for run {self.run_id}, motor {self.motor_number}; "
                f"looked for {self.path}"
            ) from exc
        except csv.Error as exc:
            raise ValueError(f"Malformed dataset CSV {self.path}: {exc}") from exc

    def _resolve_csv(self):
        filename = f"data_motor_{self.motor_number}.csv"
        root = self.dataset_root
        candidates = [
            root / filename,
            root / self.run_id / filename,
            root / "training_data" / self.run_id / filename,
            root / "training_data" / "training_data" / self.run_id / filename,
            root / "testing_data" / self.run_id / filename,
            root / "testing_data" / "testing_data" / self.run_id / filename,
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return candidates[0] if root.name == self.run_id else candidates[1]

    @staticmethod
    def _number(raw, field, line_number, required):
        if raw is None or raw == "":
            if required:
                raise ValueError(
                    f"Missing required value for {field!r} at CSV line {line_number}"
                )
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid numeric value for {field!r} at CSV line {line_number}: {raw!r}"
            ) from exc
        if not math.isfinite(value):
            raise ValueError(
                f"Non-finite value for {field!r} at CSV line {line_number}: {raw!r}"
            )
        return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--motor", required=True, type=int)
    args = parser.parse_args(argv)

    adapter = RealRobotDatasetAdapter(args.dataset_root, args.run_id, args.motor)
    observations = adapter.load_observations()
    if not observations:
        raise SystemExit("The selected motor CSV contains no observations.")

    timestamps = [item["source_metadata"]["source_timestamp"] for item in observations]
    temperatures = [
        item["telemetry"]["motor_temperature"] for item in observations
        if item["telemetry"]["motor_temperature"] is not None
    ]
    voltages = []
    for item in observations:
        raw_voltage = item["source_metadata"]["unmapped_fields"].get("voltage")
        try:
            if raw_voltage not in (None, ""):
                voltages.append(float(raw_voltage))
        except (TypeError, ValueError):
            continue

    print("REAL DATASET ADAPTER")
    print()
    print(f"Source: {SOURCE_NAME}")
    print(f"Run: {adapter.run_id}")
    print(f"Motor: {adapter.motor_number}")
    print(f"Observations: {len(observations)}")
    print(f"Time: {timestamps[0]} → {timestamps[-1]}")
    print("Temperature: " + _range(temperatures))
    print("Voltage (unmapped motor voltage): " + _range(voltages))
    print("Ground truth labels are present in source data but excluded from Genesis inference.")
    return 0


def _range(values):
    return "unavailable" if not values else f"{min(values):g} → {max(values):g}"


if __name__ == "__main__":
    raise SystemExit(main())
