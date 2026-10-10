import pandas as pd

from main import build_feature_dataset
from train_model import ReliabilityModel
from feature_contract import DEPLOYABLE_FEATURES

_, features = build_feature_dataset()

df = pd.DataFrame(features)

model = ReliabilityModel(features)
model.train()

test = df.loc[model.model1_test_index].copy()

test["probability"] = model.model.predict_proba(
    test[list(DEPLOYABLE_FEATURES)]
)[:, 1]

events = test[
    (test["failure_event"] == True)
    & test["failure_type"].notna()
][
    ["robot_id", "time_step", "motor_temperature", "failure_type"]
]

print("\n========================================")
print("VALIDATION FAILURE EVENTS")
print("========================================")
print(events.to_string(index=False))

print("\n========================================")
print("PRE-EVENT MODEL PROBABILITIES")
print("========================================")

for robot_id in events["robot_id"].unique():

    robot_events = events[events["robot_id"] == robot_id]

    for _, event in robot_events.iterrows():

        event_time = int(event["time_step"])

        rows = test[
            (test["robot_id"] == robot_id)
            & (test["time_step"] >= event_time - 10)
            & (test["time_step"] < event_time)
        ][
            [
                "robot_id",
                "time_step",
                "motor_temperature",
                "thermal_rise",
                "temperature_change",
                "probability",
            ]
        ]

        print(
            f"\n{robot_id} | "
            f"failure={event['failure_type']} | "
            f"event_time={event_time}"
        )

        print(rows.to_string(index=False))
