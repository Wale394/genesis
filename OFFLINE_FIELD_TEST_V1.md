# Offline Field Test v1

This workflow connects the existing `RealRobotDatasetAdapter` to the existing `Genesis` investigation API and report renderer. It is intended to make one recorded motor CSV reproducibly inspectable without a live robot, ROS 2, or an MQTT broker.

## Run it

From the GenesisLabcl project root:

```powershell
python offline_field_test.py --run-id 20240527_102436 --motor 1 --max-observations 100
```

By default, the dataset root is `real_data/robot-predictive-maintenance`. To use another compatible dataset root:

```powershell
python offline_field_test.py --dataset-root "C:\path\to\dataset" --run-id RUN_ID --motor 1 --output-dir my-field-test
```

The selected run must contain `data_motor_N.csv` with required `time` and `temperature` columns. `--max-observations` is optional and useful for bounded exploratory runs. The script writes `field-session.json`, `investigation-report.json`, and `investigation-report.txt` into the output directory.

## What enters Genesis

Only the adapter-produced canonical observations enter `Genesis.investigate`: the source time step, motor temperature, robot/run identity, and source metadata. The workflow does not call `load_ground_truth()`. CSV `label` values and workbook failure metadata are excluded from inference. `position` and `voltage` remain unmapped because their semantics and units are not established by the adapter.

## Interpretation boundaries

- This is recorded benchmark data, not telemetry captured live from a physical robot.
- The adapter does not independently authenticate the dataset's temperature unit; confirm the source documentation before interpreting its values as Celsius.
- This is an exploratory investigation, not a validated failure-prediction accuracy result or robot-specific diagnosis.
- A reported state or recommendation is existing prototype output, not authorization to take an operational action.

The workflow is offline and does not expose a robot-control interface.
