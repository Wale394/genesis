# Genesis Repository Organization

This is an organized copy of Genesis. The original archive was preserved separately.

## Layout

- `genesis_system/core/` — reusable evidence, history, observation, incident, comparison and temporal mechanisms.
- `genesis_system/robotics/` — robotics-specific reliability semantics and robot models.
- `genesis_system/intelligence/` — prediction/risk/warning components.
- `genesis_system/adapters/` — input translation/adapters, including ROS 2 and the real-data research adapter.
- `genesis_system/runtime/` — main Genesis runtime and decision orchestration.
- `genesis_system/interfaces/` — CLI and investigation report interfaces.
- `genesis_system/field/` — field-agent packaging/runtime.
- `offline/simulator/` — simulator and synthetic dataset generation.
- `offline/training/` — training/feature preparation.
- `offline/validation/` — offline validation and inspection experiments.
- `research/real_robot/` — external real-robot dataset experiments.
- `research/behavioral_baseline/` — behavioral-baseline prototypes already present in the project.
- `demos/` — demonstrations.

## Compatibility

Root-level compatibility shims are intentionally retained so existing scripts/tests using imports such as `from history import History` continue to work during the transition. They contain no implementation logic.

## Important

This organization is structural. It does not change Genesis decision thresholds, evidence semantics, lifecycle behavior, model behavior, or production logic.
