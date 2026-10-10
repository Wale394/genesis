# Genesis Context Behavior Experiment v0.2

## Purpose

Test one narrow hypothesis:

> Does adding label-independent operating context to the v0.1 position/voltage baseline reduce contextual-deviation detections in negative-label streams while retaining useful signal in positive-label streams?

This is a **research experiment**, not a Genesis production component.

## What changed from v0.1

The detection rule is unchanged:

- past-only baseline
- median expected temperature
- minimum 5 prior comparable observations
- deviation >= 5 C
- persistence = 3 consecutive observations

The context representation changes from:

```text
position bin + voltage bin
```

to:

```text
position bin
+ voltage bin
+ sign of previous position change
+ sign of previous voltage change
```

The labels are never used to construct the baseline or trigger the signal. They are used only after the signal is produced, for evaluation.

## Dataset

The experiment expects the real robot predictive-maintenance training CSVs containing:

```text
data_motor_*.csv
```

with columns:

```text
time, position, temperature, voltage, label
```

## Run

From the GenesisLab repository root:

```powershell
python research/context_behavior/experiment_v0_2/context_behavior_experiment_v0_2.py --data-root real_data/robot-predictive-maintenance --output-dir research/context_behavior/experiment_v0_2/results
```

If the dataset is stored elsewhere, replace `--data-root` with the directory containing the training run folders.

## Outputs

```text
results/
├── observation_results.csv
├── stream_summary.csv
├── experiment_report.json
└── experiment_report.txt
```

## Preliminary run in the assistant environment

Using the same script against the same 138 training streams:

- 138 streams
- 235,854 observations
- 17 positive-label streams
- 121 negative-label streams
- positive streams with persistent deviation: 10/17
- negative streams with persistent deviation: 7/121
- persistent observations overlapping positive labels: 462
- persistent observations in negative labels: 424
- randomized-label control overlap: 89 observations across 8 streams

These results are preliminary until reproduced in the user's GenesisLab environment.

## Interpretation discipline

This experiment does **not** establish:

- failure causation
- a deployable failure detector
- that the richer context is superior overall
- that labels describe a causal failure mechanism

The important comparison is v0.1 vs v0.2 under the same dataset and detection thresholds.
