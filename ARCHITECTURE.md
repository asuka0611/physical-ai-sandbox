# Architecture

## Boundaries

- `physical_ai_sandbox.envs`: Environment API: `reset`, `step`, `render`, `close`.
- `physical_ai_sandbox.controllers`: Manual and replay action sources.
- `physical_ai_sandbox.recording`: Episode persistence.
- `physical_ai_sandbox.evaluation`: Reward, success, and failure checks.
- `physical_ai_sandbox.scene`: YAML config loading, schema validation, and MJCF generation.

## Core API

The environment returns:

```python
observation, reward, terminated, truncated, info
```

`observation` and `action` semantics are stable contracts. Future phases can add
fields, but must not remove or change existing fields without a migration.

## Safety

Actions are clipped to `[-1.0, 1.0]`. Joint targets are then clipped to MuJoCo
joint ranges. Headless operation is first-class so future RL training does not
depend on a viewer.

## Phase 4.6 macOS Launcher Architecture

The local macOS Launcher is not a self-contained application. It starts a user LaunchAgent that runs `uv run python scripts/run_control_panel.py` in the local checkout without opening Terminal. The Tk operation panel stays in a normal Python process. The MuJoCo simulation and Viewer run in a separate `mjpython` process via `physical_ai_sandbox.ui.simulation_process`. The two processes exchange command and snapshot messages over `multiprocessing.connection` on localhost. This avoids the macOS `mjpython` + Tkinter/Tcl-Tk 9 same-process crash and keeps `mujoco.viewer.launch_passive` out of a Tk worker thread.

## Phase 5 Policy Evaluation Architecture

Phase 5 now introduces a shared `Policy` interface under `physical_ai_sandbox.policies`. Random, Manual, Behavior Cloning, and PPO adapters expose the same `reset()`, `act()`, `close()`, and `metadata()` contract while preserving the existing fixed Observation and 8D Action specifications. `physical_ai_sandbox.evaluation.policy_runner` performs headless fixed-condition grasp+lift evaluation and writes JSON/CSV results with per-episode metrics and action trajectories. `physical_ai_sandbox.evaluation.policy_compare` runs same-seed comparisons and emits JSON, CSV, and Markdown summaries. UI evaluation controls and Viewer trajectory replay are the next architecture step; see `PHASE5_COMPLETION_STATUS.md`.
