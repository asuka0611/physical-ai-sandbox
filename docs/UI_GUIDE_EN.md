# UI Guide EN

## Launch

Launch the workspace and integrated 3D Viewport:

```bash
uv run python scripts/run_control_panel.py
```

Launch with English labels:

```bash
uv run python scripts/run_control_panel.py --language en
```

The workspace runs under normal Python/Tkinter. MuJoCo simulation and offscreen
rendering run internally in a separate `mjpython` process, and rendered frames
are displayed in the central Viewport.

## Control Panel

- Shows run state, Episode, Step, Reward, Grasped, Lifted, Success, and Recording state.
- The language menu switches between Japanese and English at runtime.
- `Start`, `Pause/Resume`, `Reset`, and `Quit` control execution.
- Mode switches between `Manual Test` and `AI Recording`. Manual Test does not save episodes.
- `REC` and `Stop REC` control Episode logging while AI Recording mode is active.
- `Open Gripper` and `Close Gripper` control the gripper command.
- XYZ buttons are mapped to the fixed 8D Action contract. Observation, Action, and Dataset specs are unchanged.
- J1 through J7 `+` / `-` buttons directly control all seven arm joints.
- The step-size slider adjusts the magnitude of each manual command.

## Viewport

- Left drag: Orbit
- Shift + left drag, or middle drag: Pan
- Mouse wheel: Zoom
- Double click: focus the selected joint or return to Isometric
- `Camera Reset`: restore the default camera
- `Front`, `Right`, `Top`, `Back`, `Left`, `Bottom`, `Isometric`: preset views
- Camera Gizmo in the upper-right: click the center for Isometric, or X/Y/Z labels for preset views

## Joint Labels

- J1-J7 labels are displayed directly in the Viewport.
- Scene Tree, Viewport labels, and Robot Inspector selection stay synchronized.
- The selected joint is yellow, the Inspector row is highlighted, and the camera focuses that joint.

## Layout

- Drag the borders between Project, Viewport, Inspector, and Bottom panels to resize them.
- `Maximize Viewport` hides Project, Inspector, and Bottom.
- `Zen Mode` keeps only the Viewport visible.
- `Layout Reset` restores all panels.
- Camera, layout, hidden panels, selected joint, active tab, mode, and overlay visibility are saved on exit and restored on next launch.

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
| Esc | Clear input focus |

## Existing Viewer

The existing manual MuJoCo Viewer remains available as a separate CLI. The
Workspace ControlPanel path does not open a separate Viewer window.

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
