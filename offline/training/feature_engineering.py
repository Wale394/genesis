from collections import defaultdict

from feature_contract import (
    SIMULATOR_ONLY_FIELDS,
    build_features,
)


class FeatureEngineer:
    """Build batch features using the streaming feature contract."""

    def create_features(self, labeled_dataset):
        # Keep the original record fields for labels and historical replay,
        # but derive model features exclusively from the shared contract.
        records = [dict(record) for record in labeled_dataset]
        return self.add_temporal_features(records)

    def add_temporal_features(self, records):
        robots = defaultdict(list)
        for position, record in enumerate(records):
            robots[record["robot_id"]].append((position, record))

        result = [None] * len(records)
        for robot_records in robots.values():
            robot_records.sort(
                key=lambda item: (item[1].get("time_step", 0), item[0])
            )
            history = []
            for position, record in robot_records:
                feature_values = build_features(record, history)
                enriched = dict(record)
                enriched.update(feature_values)

                # These are simulator labels/state, not model features. Keep
                # them on dataset rows for existing evaluation and replay APIs.
                for field in SIMULATOR_ONLY_FIELDS:
                    if field in record:
                        enriched[field] = record[field]

                result[position] = enriched
                history.append(record)

        return result
