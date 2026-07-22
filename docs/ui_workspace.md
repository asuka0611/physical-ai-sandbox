# UI Workspace and Recovery

Phase 5.1-5.9 starts the transition from a demo-style control panel to a Physical AI workspace.

## Implemented MVP

- Dock-style Tk workspace with toolbar, scene/policy sidebar, embedded 3D Viewport, robot inspector, and bottom Console/Metrics/Evaluation/Timeline tabs.
- Central `InputManager` for keyboard focus and shortcut dispatch.
- Text entry focus blocks robot shortcuts such as W/A/S/D and Space.
- Escape clears text focus instead of quitting the app.
- Toolbar controls for Reset, Restart Viewport, Restart All, Emergency Stop, and Camera Reset.
- MuJoCo offscreen RGB frames are streamed from the `mjpython` simulation process into the central Tk Canvas.
- Viewport camera controls:
  - left drag: Orbit
  - Shift + left drag or middle drag: Pan
  - mouse wheel: Zoom
  - double click: focus selected joint or return to Isometric
  - toolbar buttons: Camera Reset and Front/Right/Top/Back/Left/Bottom/Isometric presets
- Camera state is sent through IPC and saved/restored with the workspace state.
- A simple Viewport camera gizmo is drawn in the upper-right. Clicking the center returns to Isometric; axis labels switch to Top, Front, or Right.
- J1-J7 labels are projected from MuJoCo joint label sites into a Canvas overlay. The selected joint is highlighted in yellow and the Scene Tree, Inspector, overlay, and camera focus are synchronized.
- Horizontal and vertical panes are resizable. Viewport Maximize hides Project/Inspector/Bottom panels; Zen Mode keeps only the Viewport; Layout Reset restores all panels.
- Layout, hidden panels, active tab, selected joint, mode, overlay visibility, and camera state are persisted under `~/Library/Application Support/Physical AI Sandbox/workspace_state.json`.
- Manual Test mode is separated from AI Recording mode. Manual Test blocks recording writes; AI Recording exposes REC/Stop REC and displays a red REC overlay while active.
- Idle rendering is throttled: the simulation process renders at the target frame rate while running, but paused scenes only re-render on camera/layout changes or a low-frequency heartbeat.
- Background evaluation subprocess from the Evaluation tab.
- Viewport process restart loop guard.

## Current Limits

- The official MuJoCo Viewer window is not opened from the ControlPanel path.
- The embedded Viewport is frame-stream based and does not expose native MuJoCo Viewer menus.
- Joint click selection uses projected 2D label hit targets rather than true geometry picking.
- Timeline replay UI is a placeholder; action trajectories are saved by policy evaluation JSON.
- Long-run memory-leak verification still requires a longer manual run.

## Screenshot

![Workspace UI](screenshots/workspace_ui_phase_2026-07-22.png)
