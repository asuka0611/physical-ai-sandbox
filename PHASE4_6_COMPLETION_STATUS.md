# Phase 4.6 Completion Status

Last verified: 2026-07-22

## Implemented

- Replaced the self-contained py2app distribution plan with a local-only macOS startup Launcher.
- Added `dist/Physical AI Sandbox Launcher.app` build flow using a small Swift/Cocoa launcher.
- The Launcher starts a user LaunchAgent and then exits; Terminal is not opened.
- The LaunchAgent runs the existing local development command with normal Python:

```bash
cd "/Users/miyachiasuka/Documents/prog/Physical AI Sandbox"
uv run python scripts/run_control_panel.py
```

- The Tkinter operation panel and MuJoCo Viewer are now separated:
  - UI process: normal Python + Tkinter.
  - Simulation process: `uv run mjpython -m physical_ai_sandbox.ui.simulation_process`.
  - IPC: `multiprocessing.connection` command/state messages over localhost.
- `mujoco.viewer.launch_passive` is called from the simulation process main execution path, not from a Python worker thread.
- Added Japanese startup failure dialogs and crash reports for Viewer process failures.
- Added logs under `~/Library/Logs/Physical AI Sandbox Launcher/` and simulation logs under the app log directory.
- Added duplicate-process prevention for `run_control_panel.py`.
- Added clean process-group termination from the Tk UI so `uv`/`mjpython` children do not remain.
- Kept `scripts/run_control_panel.py` as the primary local UI entry point.
- Removed the adopted packaging path's dependency on py2app, bundled Python, bundled MuJoCo, Developer ID signing, notarization, and Intel packaging.

## Output

```text
dist/Physical AI Sandbox Launcher.app
```

Bundle Identifier:

```text
com.asuka0611.physical-ai-sandbox.launcher
```

## Verification Results

- `uv sync`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 80 tests.
- `uv run python scripts/validate_config.py`: passed.
- `uv run python scripts/run_headless.py --steps 1000`: passed.
- `bash scripts/build_macos_app.sh`: passed; generated `dist/Physical AI Sandbox Launcher.app`.
- `open -n "dist/Physical AI Sandbox Launcher.app"`: passed.
- Operation panel window: observed as `Physical AI Sandbox`.
- MuJoCo Viewer window: observed as `MuJoCo : physical_ai_sandbox_panda_pick_place`.
- Viewer visual pass: screenshot confirmed robot/table/cube rendered in MuJoCo Viewer.
- UI operation pass: keyboard commands advanced the UI step counter and changed the latest action to `gripper open` while Viewer was visible.
- Duplicate launch pass: second Launcher invocation logged `既に起動中です` and did not create another Control Panel/Viewer process.
- Terminal pass: no new Terminal window was opened; only the pre-existing Terminal process remained.
- Shutdown pass: closing the operation panel removed `run_control_panel.py`, simulation process, and `mjpython` processes.

## Non-Goals

- This is not a distributable app.
- Python, MuJoCo, datasets, checkpoints, and dependencies are not bundled.
- Developer ID signing, notarization, Hardened Runtime, and Intel support are not part of this local Launcher.
- Public distribution packaging remains out of scope.
