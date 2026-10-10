# Context Behavior Experiment v0.1

## Engineering question
Can a system compare an observation with what it previously observed under comparable operating context, and detect persistent behavioral deviation without using the failure label to construct the baseline?

## Method
For each motor stream, process observations chronologically. Use only earlier observations to build a median temperature baseline for the current `(position bin, voltage bin)` context. Require five prior observations in that context. Flag a temperature deviation of at least 5 C for three consecutive observations.

Labels are used only after the signal is produced, for evaluation. They never enter baseline construction.

A randomized-label control shuffles labels within each stream with a fixed seed, preserving telemetry and the detected deviations.

## Run
From the GenesisLab root, if the dataset is stored as `data/robot-predictive-maintenance/training_data/training_data/...`:

```powershell
python research/context_behavior/experiment_v0_1/context_behavior_experiment.py --data-root data/robot-predictive-maintenance --output-dir research/context_behavior/experiment_v0_1/results
```

Or point `--data-root` directly at the directory containing the run folders.

## Outputs
- `observation_results.csv`
- `stream_summary.csv`
- `experiment_report.json`
- `experiment_report.txt`

This is a research prototype. It does not modify Genesis production behavior and is not a failure detector.
