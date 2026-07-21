# Phase 4.6 Completion Status

Last verified: 2026-07-21

## Implemented

- Replaced the self-contained py2app distribution plan with a local-only macOS startup Launcher.
- Added `dist/Physical AI Sandbox Launcher.app` build flow using a small Swift/Cocoa launcher.
- The Launcher runs the existing local development command without opening Terminal:

```bash
cd "/Users/miyachiasuka/Documents/prog/Physical AI Sandbox"
uv run mjpython scripts/run_control_panel.py
```

- Added project-folder access handling for macOS Documents privacy via `NSOpenPanel`.
- Added Japanese startup failure dialogs with log file location.
- Added logs under `~/Library/Logs/Physical AI Sandbox Launcher/` and `latest.log` symlink.
- Added duplicate-process prevention for `run_control_panel.py`.
- Added PID recording in `control-panel.pid`.
- Kept `scripts/run_control_panel.py` and the existing GUI/runtime path unchanged.
- Removed the adopted packaging path's dependency on py2app, bundled Python, bundled MuJoCo, Developer ID signing, notarization, and Intel packaging.
- Updated macOS packaging tests for the local Launcher strategy.

## Output

```text
dist/Physical AI Sandbox Launcher.app
```

Bundle Identifier:

```text
com.asuka0611.physical-ai-sandbox.launcher
```

## Local Requirements

- Project path: `/Users/miyachiasuka/Documents/prog/Physical AI Sandbox`
- `uv` installed and visible from the login shell PATH.
- `uv sync` already completed.
- `mjpython` available through `uv run mjpython`.
- macOS project-folder access granted on first launch if prompted.

## Verification Results

- `uv sync`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 77 tests.
- `uv run python scripts/validate_config.py`: passed.
- `uv run python scripts/run_headless.py --steps 1000`: passed.
- `bash scripts/clean_macos_build.sh`: passed.
- `bash scripts/build_macos_app.sh`: passed; generated `dist/Physical AI Sandbox Launcher.app`.
- Direct `open -n "dist/Physical AI Sandbox Launcher.app"`: reached the local Launcher startup flow and opened the macOS project-folder access flow.
- Terminal window check: no new Terminal window was opened; the pre-existing Terminal process was unchanged.
- Failure dialog path: observed Japanese startup error dialogs during earlier AppleScript/TCC failure tests.
- Log path: verified `~/Library/Logs/Physical AI Sandbox Launcher/latest.log` creation.

## Manual GUI Check Status

A full MuJoCo Viewer visual confirmation is still blocked until the first-launch macOS folder access panel is accepted by the user for the project under `~/Documents`.

Required manual pass after accepting the folder access panel:

- Operation panel is visible.
- MuJoCo 3D Viewer is visible in a separate window.
- Robot, table, and cube are visible.
- Terminal window is not opened by the Launcher.
- Launching twice does not create duplicate `run_control_panel.py` processes.
- Closing the GUI leaves no unnecessary Launcher or Control Panel process.
- Logs are saved under `~/Library/Logs/Physical AI Sandbox Launcher/`.

## Non-Goals

- This is not a distributable app.
- Python, MuJoCo, datasets, checkpoints, and dependencies are not bundled.
- Developer ID signing, notarization, Hardened Runtime, and Intel support are not part of this local Launcher.
- The newer IPC-based app architecture is not used in this phase.
