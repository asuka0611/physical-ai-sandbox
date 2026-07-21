# Physical AI Sandbox

MuJoCo-based Physical AI sandbox for a Panda-style 7-axis robot arm. The project
now includes the Phase 1 manual-control environment, Phase 2 dataset pipeline,
Phase 3 offline Behavior Cloning training, Phase 3.5 closed-loop BC rollout
safety evaluation, Phase 4 PPO smoke training, and Phase 4.5 Japanese UI /
visual refresh.

## Requirements

- Python 3.11
- uv
- macOS, Linux, or another platform supported by MuJoCo Python

## Setup

```bash
uv sync
```

## Validate

```bash
uv run ruff check .
uv run pytest
uv run python scripts/validate_config.py
```

## Run Headless

```bash
uv run python scripts/run_headless.py --steps 1000
```

This runs reset, step, reward, success/failure checks, and optional logging
without opening a viewer.

## Run Manual Viewer

On macOS, MuJoCo's interactive viewer must be launched through `mjpython`:

```bash
uv run mjpython scripts/run_manual.py
```

On non-macOS platforms, normal Python is usually sufficient:

```bash
uv run python scripts/run_manual.py
```

Controls:

| Key | Action |
|---|---|
| 1-7 | Select joint directly |
| Tab or ] | Select next joint |
| [ | Select previous joint |
| Left arrow | Move selected joint negative |
| Right arrow | Move selected joint positive |
| Space | Toggle gripper |
| R | Reset |
| P | Pause |
| L | Toggle episode recording |
| C | Reset camera |
| Esc | Quit |

The MuJoCo passive viewer does not expose Shift modifiers consistently across
MuJoCo versions, so `[` is the reliable previous-joint fallback for Shift+Tab.
Headless operation remains the supported path for automated tests and future
reinforcement learning.


## Run Japanese Control Panel

Launch the Tkinter control panel with the MuJoCo Viewer:

```bash
uv run mjpython scripts/run_control_panel.py
```

Launch in English:

```bash
uv run mjpython scripts/run_control_panel.py --language en
```

The package entrypoint is also available:

```bash
uv run physical-ai-control-panel --language ja
```

The control panel keeps MuJoCo simulation on a worker thread and sends UI
commands through a thread-safe command queue. It displays run state, Episode,
Step, Reward, Grasped, Lifted, Success, Recording, Controller, and the latest
manual event. It supports start, pause/resume, reset, quit, recording
start/stop, gripper open/close, camera reset, XYZ-style movement buttons,
rotation buttons, direct J1-J7 joint buttons, and a command-size slider.

Control-panel keyboard bindings:

| Key | Action |
|---|---|
| W / S | Forward / backward |
| A / D | Left / right |
| R / F | Up / down |
| Q / E | Rotate |
| O | Open gripper |
| C | Close gripper |
| Space | Pause / resume |
| Enter | Reset |
| Esc | Quit |

Detailed guides:

- `docs/UI_GUIDE_JA.md`
- `docs/UI_GUIDE_EN.md`

Screenshot placement: add UI screenshots under `docs/screenshots/`.

## Run Pick-and-Place Demo

```bash
uv run python scripts/run_pick_place_demo.py --record
```

To smoke-test Viewer startup and cleanup while showing the final state:

```bash
uv run python scripts/run_pick_place_demo.py --viewer --record --hold-seconds 1
```

The demo closes the gripper, grasps the cube, moves it to the target region,
opens the gripper, waits for the success-stability window, and records an
episode when `--record` is set. On macOS, the final-state Viewer is launched in
a child `mjpython` process so the parent process can clean it up if the GUI
backend hangs.

## Replay an Episode

```bash
uv run python scripts/replay_episode.py logs/episodes/episode_YYYYMMDD_HHMMSS
```

Replay reads the saved `steps.jsonl` actions and applies them to a fresh
environment. It is intended for behavior checks, bug reproduction, and dataset
audits.

## Scene Configuration

The default scene lives at `configs/default.yaml`.

Obstacles are declared in YAML and validated by `schemas/scene_config.schema.json`.
Phase 1 supports `box` and `cylinder`.

```yaml
objects:
  - id: obstacle_1
    type: box
    position: [0.50, 0.15, 0.85]
    size: [0.10, 0.20, 0.30]
    static: true
    collision: true
```


### UI and Visual Settings

```yaml
ui:
  language: ja
  theme: dark
  show_control_panel: true
  show_status_overlay: true
robot_visual:
  theme: modern_lab
  accent_color: blue
```

Older configs without these keys remain valid; defaults are applied by the
config loader. Japanese strings are used only in the display layer. Internal
body, joint, actuator, site, Observation, Action, Dataset, and checkpoint
contracts remain English and unchanged.

### Visual Refresh

The default generated MJCF now uses a modern lab-arm visual theme: off-white
robot covers, dark-gray joints, blue accent rings, dark gripper covers, an
orange cube, green translucent target/place markers, blue translucent pick
marker, red obstacles, neutral-gray table, and a dark grid floor. Added covers,
rings, plates, cables, and area markers are visual-only geoms with collision
disabled so the existing physics contract is preserved.

## Action Contract

Actions are fixed as eight floats:

```python
[
    joint_1_delta,
    joint_2_delta,
    joint_3_delta,
    joint_4_delta,
    joint_5_delta,
    joint_6_delta,
    joint_7_delta,
    gripper_command,
]
```

Joint deltas and gripper command are clipped to `[-1.0, 1.0]` before use.

## Observation Contract

Every observation contains:

- `joint_positions`: `float[7]`
- `joint_velocities`: `float[7]`
- `gripper_positions`: `float[2]`
- `cube_position`: `float[3]`
- `cube_rotation`: `float[4]`
- `end_effector_position`: `float[3]`
- `is_grasped`: `bool`
- `is_success`: `bool`
- `elapsed_time`: `float`

These fields are stable API for downstream dataset, imitation learning, and
reinforcement learning work.


## Build Phase 2 Dataset

Build a Behavior-Cloning-ready dataset from Phase 1 episode logs:

```bash
uv run python scripts/build_dataset.py \
  --episodes logs/episodes \
  --output datasets/pick_place_v1 \
  --seed 42
```

Validate the dataset:

```bash
uv run python scripts/validate_dataset.py datasets/pick_place_v1
```

Inspect a short summary:

```bash
uv run python scripts/inspect_dataset.py datasets/pick_place_v1
```

Dataset output structure:

```text
datasets/pick_place_v1/
├── train.npz
├── validation.npz
├── test.npz
├── metadata.json
├── statistics.json
├── quality_report.json
└── manifest.json
```

Saved arrays:

- `observations`
- `actions`
- `rewards`
- `terminated`
- `truncated`
- `success`
- `episode_ids`
- `step_indices`

Splits are made by Episode, not by step, so the same Episode cannot appear in
multiple splits. The builder records broken Episode directories in
`quality_report.json` and excludes them from the built dataset unless strict mode
is requested.


## Train Phase 3 Behavior Cloning

Train the initial Behavior Cloning policy on a Phase 2 dataset:

```bash
uv run python scripts/train_behavior_cloning.py \
  --dataset datasets/pick_place_v1 \
  --output models/bc_pick_place_v1 \
  --epochs 80 \
  --seed 42
```

Evaluate a saved checkpoint:

```bash
uv run python scripts/evaluate_behavior_cloning.py \
  models/bc_pick_place_v1 \
  --dataset datasets/pick_place_v1
```

Model output structure:

```text
models/bc_pick_place_v1/
├── policy_checkpoint.npz
├── metadata.json
├── training_history.json
└── evaluation_report.json
```

Phase 3 currently uses a small NumPy MLP for Behavior Cloning pipeline
verification. The current dataset has only 5 valid Episodes and a 5-sample test
split, so evaluation metrics are supervised Action-prediction smoke-test metrics,
not evidence of robot-task performance.


## Phase 3.5 Behavior Cloning Rollout

Run a trained BC checkpoint through the Environment API in headless mode:

```bash
uv run python scripts/evaluate_bc_rollout.py \
  models/bc_pick_place_v1 \
  --episodes 3 \
  --max-steps 200 \
  --seed 42
```

The rollout CLI loads `policy_checkpoint.npz`, applies the same Observation
normalization saved during training, clips the fixed 8D Action, stops safely on
NaN/Inf output, records rollout Episodes under `logs/bc_rollouts`, replays
recorded actions, and writes `rollout_report.json`.

Reported rollout metrics include success rate, average reward, grasp rate, lift
rate, goal-reaching rate, replay count, and aggregated failure reasons. With the
current 5-Episode dataset, these metrics verify pipeline safety only; they are
not evidence of robot-control performance or generalization.


## Phase 3.6 Fixed-Condition Grasp+Lift Data

Collect fixed-initial-condition grasp+lift demonstrations:

```bash
uv run python scripts/collect_grasp_lift_demos.py \
  --episodes 30 \
  --output logs/grasp_lift_demos \
  --seed 42 \
  --overwrite
```

Build and validate the simplified-task dataset:

```bash
uv run python scripts/build_dataset.py \
  --episodes logs/grasp_lift_demos \
  --output datasets/grasp_lift_v1 \
  --name grasp_lift \
  --version v1 \
  --seed 42
uv run python scripts/validate_dataset.py datasets/grasp_lift_v1
```

Train and rollout-evaluate the simplified-task BC checkpoint:

```bash
uv run python scripts/train_behavior_cloning.py \
  --dataset datasets/grasp_lift_v1 \
  --output models/bc_grasp_lift_v1 \
  --epochs 120 \
  --seed 42
uv run python scripts/evaluate_bc_rollout.py \
  models/bc_grasp_lift_v1 \
  --episodes 10 \
  --max-steps 120 \
  --seed 42 \
  --log-root logs/bc_grasp_lift_rollouts
```

Phase 3.6 keeps the task intentionally narrow: fixed initial cube/robot state,
immediate gripper close, then lift. The generated `datasets/grasp_lift_v1` has
30 Episodes and 1800 samples. The resulting rollout report tracks both the
original Pick-and-Place `success_rate` and the simplified-task
`grasp_lift_success_rate`; only the latter applies to this phase. These numbers
are fixed-condition evaluation results, not generalization or full Pick-and-Place
performance claims.


## Phase 4 PPO Smoke Training

Train a short fixed-condition grasp+lift PPO smoke run from the Phase 3.6 BC checkpoint:

```bash
uv run python scripts/train_ppo.py \
  --output models/ppo_grasp_lift_bc_smoke \
  --dataset datasets/grasp_lift_v1 \
  --bc-model models/bc_grasp_lift_v1 \
  --init bc \
  --total-steps 256 \
  --rollout-steps 64 \
  --max-episode-steps 120 \
  --seed 42
```

Evaluate a saved PPO checkpoint:

```bash
uv run python scripts/evaluate_ppo.py \
  models/ppo_grasp_lift_bc_smoke \
  --episodes 5 \
  --max-steps 120 \
  --seed 42
```

Compare BC-only, random PPO, and BC-initialized PPO smoke runs:

```bash
uv run python scripts/compare_ppo.py \
  --output models/ppo_phase4_smoke_compare \
  --dataset datasets/grasp_lift_v1 \
  --bc-model models/bc_grasp_lift_v1 \
  --episodes 3 \
  --max-steps 120 \
  --total-steps 128 \
  --rollout-steps 64 \
  --seed 42
```

Phase 4 PPO is intentionally a short End-to-End smoke pipeline: Environment,
rollout buffer, GAE, clipped PPO objective, value loss, entropy term, gradient
clipping, checkpoint save/reload, resume, evaluation, and comparison reporting.
The initial task remains fixed-initial-condition grasp+lift. PPO can degrade
from the BC-only baseline, and these smoke results are not full Pick-and-Place or
generalization evidence.


## macOS Application Bundle

Build a macOS `.app` bundle:

```bash
bash scripts/clean_macos_build.sh
bash scripts/build_macos_app.sh
```

Output:

```text
dist/Physical AI Sandbox.app
```

Launch the bundled app:

```bash
open "dist/Physical AI Sandbox.app"
```

The bundled app prepares Application Support and runs the control panel/runtime
in the app process. Development launches still use managed subprocess cleanup,
but the signed `.app` avoids spawning a second app executable from LaunchServices.
Writable app data is stored under:

```text
~/Library/Application Support/Physical AI Sandbox/
```

The first launch copies `configs/default.yaml` into Application Support if it is
missing. Runtime logs, replays, datasets, models, and crash reports also live
under that directory. Phase 4.6 uses Ad Hoc signing only; Developer ID signing,
notarization, and stapling are not complete.

Detailed guides:

- `docs/MACOS_APP_GUIDE_JA.md`
- `docs/MACOS_APP_GUIDE_EN.md`

## Current Phase 1 Status

Implemented:

- MuJoCo scene with floor, table, Panda-style 7-axis arm, two-finger gripper,
  cube, target region, and YAML obstacles.
- Fixed Action and Observation contracts.
- Safe action clipping.
- Headless reset/step/reward/success/failure checks.
- Episode logging to `logs/episodes`.
- Action replay.
- JSON Schema validation for config.
- pytest coverage for config, environment, recorder, replay, obstacles, reset
  stability, and NaN checks.

Known limitations are tracked in `KNOWN_ISSUES.md`. Detailed Phase 1 completion status is in `PHASE1_COMPLETION_STATUS.md`.
