def is_supervised_training_eligible(record):
    """Whether a labeled row has a complete fixed horizon and binary target.

    ``horizon_valid`` is set only by the label generator after checking that
    all configured future observations exist. Parse its CSV representation
    explicitly so the string ``"False"`` cannot become truthy.
    """
    horizon_valid = record.get("horizon_valid")
    if isinstance(horizon_valid, str):
        horizon_valid = horizon_valid.strip().lower() in {"true", "1"}
    else:
        try:
            horizon_valid = bool(horizon_valid) and float(horizon_valid) == 1.0
        except (TypeError, ValueError):
            horizon_valid = False

    label = record.get("label")
    if isinstance(label, str):
        label = label.strip()
        if label not in {"0", "1"}:
            return False
        label = int(label)
    else:
        try:
            numeric_label = float(label)
        except (TypeError, ValueError):
            return False
        if numeric_label not in (0.0, 1.0):
            return False

    return horizon_valid and label in (0, 1)


def supervised_training_eligibility_mask(records):
    """Return the shared per-row eligibility mask for risk/diagnosis fitting."""
    return [is_supervised_training_eligible(record) for record in records]


class LabelGenerator:

    def __init__(self, prediction_window=10):
        self.prediction_window = prediction_window

    def create_labels(self, dataset):

        labeled_dataset = []

        # Group records by robot
        robots = {}

        for record in dataset:

            robot_id = record["robot_id"]

            if robot_id not in robots:
                robots[robot_id] = []

            robots[robot_id].append(record)

        # Label each robot's own chronological trajectory. Dataset generation
        # already emits this order; sorting also makes imported trajectories
        # respect their existing time_step representation.
        for robot_id, records in robots.items():
            indexed_records = list(enumerate(records))
            try:
                indexed_records.sort(
                    key=lambda item: (float(item[1].get("time_step")), item[0])
                )
            except (TypeError, ValueError):
                # Preserve input order when a trajectory does not provide
                # consistently parseable time_step values.
                pass
            records = [record for _position, record in indexed_records]

            for index, record in enumerate(records):

                future_records = records[
                    index + 1:
                    index + 1 + self.prediction_window
                ]

                upcoming_event = 0
                upcoming_failure_type = "none"

                for future_record in future_records:

                    # IMPORTANT:
                    # Only an actual failure event creates
                    # a future-failure label.
                    #
                    # failure_type is historical information
                    # and may remain after recovery.

                    if future_record.get(
                        "failure_event",
                        False
                    ):

                        upcoming_event = 1

                        upcoming_failure_type = (
                            future_record.get(
                                "failure_type",
                                "none"
                            )
                        )

                        break

                labeled_record = record.copy()

                # A negative label is only conclusive when the entire
                # prediction horizon was observed. Preserve censored records
                # in the dataset, but mark their supervised target unknown.
                horizon_valid = (
                    len(future_records) == self.prediction_window
                )
                labeled_record["horizon_valid"] = horizon_valid
                labeled_record["future_observations"] = len(future_records)
                labeled_record["label"] = (
                    upcoming_event if horizon_valid else None
                )

                labeled_record[
                    "failure_type_label"
                ] = upcoming_failure_type if horizon_valid else None

                labeled_dataset.append(
                    labeled_record
                )
        return labeled_dataset
