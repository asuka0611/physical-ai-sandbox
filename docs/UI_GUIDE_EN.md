# UI Guide EN

## Launch

Launch the control panel and MuJoCo Viewer together:

```bash
uv run mjpython scripts/run_control_panel.py
```

Launch with English labels:

```bash
uv run mjpython scripts/run_control_panel.py --language en
```

Use `mjpython` on macOS because the MuJoCo interactive viewer requires it.

## Control Panel

- Shows run state, Episode, Step, Reward, Grasped, Lifted, Success, and Recording state.
- The language menu switches between Japanese and English at runtime.
- `Start`, `Pause/Resume`, `Reset`, and `Quit` control execution.
- `Start Recording` and `Stop Recording` control Episode logging.
- `Open Gripper` and `Close Gripper` control the gripper command.
- XYZ buttons are mapped to the fixed 8D Action contract. Observation, Action, and Dataset specs are unchanged.
- J1 through J7 `+` / `-` buttons directly control all seven arm joints.
- The step-size slider adjusts the magnitude of each manual command.

## Keyboard

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

## Existing Viewer

The existing manual viewer remains available:

```bash
uv run mjpython scripts/run_manual.py
```

`run_manual.py` uses joint-selection controls. See the README Manual Viewer table for its exact key bindings.

## Visual Design

- The robot uses off-white covers, dark-gray joints, and blue accents for a modern lab-arm appearance.
- Added shell covers, joint covers, link covers, accent rings, cable-like visuals, and a logo plate are visual-only geoms.
- Target, pick, and place areas are translucent.
- Visual-only geoms use `contype=0`, `conaffinity=0`, and `density=0` so they do not affect collisions or inferred mass.

## Screenshots

Place screenshots under `docs/screenshots/` when available.
