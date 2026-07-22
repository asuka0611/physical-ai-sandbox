# Phase 5.1-5.9 Status

Last updated: 2026-07-22

## Implemented MVP

- Phase 5.1 UI Foundation: Dock-style workspace layout, toolbar, sidebar, inspector, bottom tabs, minimum window size.
- Phase 5.2 Input Management: centralized `InputManager`, text-entry shortcut blocking, Escape focus clearing, key-repeat suppression.
- Phase 5.3 Recovery: Restart Viewport/Restart All/Emergency Stop controls and runtime restart loop guard.
- Phase 5.4 3D Viewport: stable two-process architecture retained, but the external MuJoCo Viewer window is no longer opened from the ControlPanel path. The `mjpython` simulation process renders RGB frames offscreen and streams them into the central Tk Viewport.
- Viewport Camera UX: Orbit, Pan, Zoom, double-click focus, Camera Reset, Front/Right/Top/Back/Left/Bottom/Isometric presets, simple Camera Gizmo, and camera state persistence are implemented over IPC.
- Phase 5.5 Robot Visuals: visual-only motor housings and J1-J7 label sites added without changing collision or Action/Observation contracts. J1-J7 are also projected into the Viewport Canvas overlay.
- Joint Selection Sync: Scene Tree, Viewport label hit targets, Inspector row highlight, selected-joint status, and camera focus are synchronized.
- Layout UX: left/right/bottom panes are draggable; Viewport Maximize, Zen Mode, panel visibility, active tab, selected joint, mode, overlay visibility, and camera state are persisted.
- Mode Separation: Manual Test blocks recording writes; AI Recording enables REC/Stop REC and shows a red REC overlay when recording.
- Manual Test Session Stability: reaching 1000 steps no longer ends the episode, resets simulation, saves trajectory data, or reinitializes robot/object state. Manual Test state persists until the user presses Reset.
- Phase 5.6 Policy/Evaluation UI: Policy/model/episode/seed controls and background evaluation subprocess added.
- Phase 5.7 Metrics: status/metrics panel shows live simulation snapshot values; exported comparison metrics remain available through CLI.
- Phase 5.8 Replay: action trajectories are saved by policy evaluation JSON; Timeline tab documents replay entry point.
- Phase 5.9 Stability/UX: crash-safe process split retained; input, restart, process lifecycle tests, and idle render throttling added.

## Not Full Completion Yet

- Native MuJoCo Viewer menus are not embedded; the implemented Viewport is a frame-stream renderer with custom camera controls.
- Viewer trajectory playback controls are not complete.
- UI evaluation progress parsing is minimal.
- 10-minute continuous memory verification has not been run in this pass.
- Joint click selection uses projected label hit targets, not full 3D geometry picking.

## Verification Targets

- Ruff and pytest must pass.
- macOS Launcher must still open without Terminal.
- Embedded Viewport must be visually checked after UI layout changes.
- Exit must leave no `run_control_panel.py`, simulation process, or `mjpython` process.
- Manual checks should include camera Orbit/Pan/Zoom, preset buttons, joint label selection, Viewport Maximize/Zen Mode, Manual Test recording block, AI Recording REC indicator, and layout restore after restart.
