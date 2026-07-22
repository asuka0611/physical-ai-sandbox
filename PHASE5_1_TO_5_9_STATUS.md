# Phase 5.1-5.9 Status

Last updated: 2026-07-22

## Implemented MVP

- Phase 5.1 UI Foundation: Dock-style workspace layout, toolbar, sidebar, inspector, bottom tabs, minimum window size.
- Phase 5.2 Input Management: centralized `InputManager`, text-entry shortcut blocking, Escape focus clearing, key-repeat suppression.
- Phase 5.3 Recovery: Restart Viewer/Restart All/Emergency Stop controls and runtime restart loop guard.
- Phase 5.4 Viewer Workspace: stable two-process architecture retained, macOS best-effort Viewer front/position reset controls added.
- Phase 5.5 Robot Visuals: visual-only motor housings and J1-J7 label sites added without changing collision or Action/Observation contracts.
- Phase 5.6 Policy/Evaluation UI: Policy/model/episode/seed controls and background evaluation subprocess added.
- Phase 5.7 Metrics: status/metrics panel shows live simulation snapshot values; exported comparison metrics remain available through CLI.
- Phase 5.8 Replay: action trajectories are saved by policy evaluation JSON; Timeline tab documents replay entry point.
- Phase 5.9 Stability/UX: crash-safe process split retained; input, restart, and process lifecycle tests added.

## Not Full Completion Yet

- Full native embedded Viewport is not adopted.
- Viewer trajectory playback controls are not complete.
- UI evaluation progress parsing is minimal.
- 10-minute continuous memory verification has not been run in this pass.
- Dynamic 3D selected-joint highlight is not complete; joint selection is reported through UI/snapshot/overlay status first.

## Verification Targets

- Ruff and pytest must pass.
- macOS Launcher must still open without Terminal.
- Viewer must be visually checked after UI layout changes.
- Exit must leave no `run_control_panel.py`, simulation process, or `mjpython` process.
