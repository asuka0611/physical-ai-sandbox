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

## Phase 5 Planned Architecture

Phase 5 should introduce a shared Policy interface and a policy evaluation runner before UI integration. Planned adapters are Manual, Random, Behavior Cloning, and PPO. Evaluation output should support per-episode JSON/CSV records and same-seed policy comparison. See `PHASE5_PLAN.md`.
