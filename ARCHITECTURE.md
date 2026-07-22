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

The local macOS Launcher is not a self-contained application. It starts `uv run python scripts/run_control_panel.py` directly from the GUI app process without opening Terminal. The Tk operation panel stays in a normal Python process. MuJoCo simulation and offscreen rendering run in a separate `mjpython` process via `physical_ai_sandbox.ui.simulation_process`. The two processes exchange command, snapshot, and PPM frame messages over `multiprocessing.connection` on localhost. This avoids the macOS `mjpython` + Tkinter/Tcl-Tk 9 same-process crash and keeps `mujoco.viewer.launch_passive` out of the ControlPanel path.

## Phase 5 Policy Evaluation Architecture

Phase 5 now introduces a shared `Policy` interface under `physical_ai_sandbox.policies`. Random, Manual, Behavior Cloning, and PPO adapters expose the same `reset()`, `act()`, `close()`, and `metadata()` contract while preserving the existing fixed Observation and 8D Action specifications. `physical_ai_sandbox.evaluation.policy_runner` performs headless fixed-condition grasp+lift evaluation and writes JSON/CSV results with per-episode metrics and action trajectories. `physical_ai_sandbox.evaluation.policy_compare` runs same-seed comparisons and emits JSON, CSV, and Markdown summaries. UI evaluation controls and Viewer trajectory replay are the next architecture step; see `PHASE5_COMPLETION_STATUS.md`.

## Phase 5.1-5.9 Workspace MVP

The UI keeps the Phase 4.6 two-process split: Tkinter runs in normal Python, while MuJoCo simulation and rendering remain in a separate `mjpython` process. Instead of opening the official MuJoCo Viewer window, the simulation process uses MuJoCo's offscreen `Renderer`, encodes RGB frames as PPM, and streams them into a Tk Canvas in the central 3D Viewport. Camera Orbit/Pan/Zoom, presets, focus, and reset are represented as IPC commands and applied inside the simulation process before rendering. The renderer returns frame metadata including camera state, projected J1-J7 label positions, FPS, and simulation Hz.

The Tk surface is organized as a workspace with toolbar, scene/policy sidebar, embedded Viewport, robot inspector, and bottom tabs. `InputManager` centralizes keyboard focus so Entry-like widgets do not dispatch robot shortcuts. Layout state, hidden panels, active tab, selected joint, mode, overlay visibility, and camera state are persisted in the local Application Support workspace state file.

Robot visual changes are MJCF visual-only additions: J1-J7 motor housings and label sites. They do not change collision geoms, actuators, Observation, or the fixed 8D Action contract.

## Phase 6/7 MVP Architecture

`physical_ai_sandbox.robotics` adds a Sim2Real-facing `RobotInterface`, `SimulationRobot`, `MockRealRobot`, and `SafetyLayer`. `physical_ai_sandbox.perception` adds `CameraSource`, `MockCamera`, `ObjectPerception`, and `ObservationBuilder`. These layers record provenance such as `execution_backend`, `camera_source`, `object_pose_source`, `hardware_connected`, and `real_world_validated` to avoid fake real-world claims.
