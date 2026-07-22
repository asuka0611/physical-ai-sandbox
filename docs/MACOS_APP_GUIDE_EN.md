# macOS Launcher Guide EN

## Overview

`Physical AI Sandbox Launcher.app` is not a distributable application. It is a local-only launcher for this Mac's development checkout.

Double-clicking it runs the equivalent of the following command without opening a Terminal window:

```bash
cd "/Users/miyachiasuka/Documents/prog/Physical AI Sandbox"
uv run python scripts/run_control_panel.py
```

The operation panel runs under normal Python/Tkinter. MuJoCo simulation and
offscreen rendering run in a separate `mjpython` process, and rendered frames
are displayed in the central 3D Viewport. The ControlPanel path does not open a
separate MuJoCo Viewer window.

## Requirements

- The project exists at `/Users/miyachiasuka/Documents/prog/Physical AI Sandbox`.
- `uv` is installed.
- `uv sync` has already completed.
- `uv run mjpython` is available.

## Build

```bash
bash scripts/clean_macos_build.sh
bash scripts/build_macos_app.sh
```

Output:

```text
dist/Physical AI Sandbox Launcher.app
```

## Launch

```bash
open -n "dist/Physical AI Sandbox Launcher.app"
```

The Launcher starts the local UI directly from the GUI app process without opening Terminal. Duplicate launches detect the existing `run_control_panel.py` process instead of creating another one.

## Logs

```text
~/Library/Logs/Physical AI Sandbox Launcher/
```

Startup failures are shown in a Japanese dialog with the log path.

## Notes

The Launcher does not bundle Python, MuJoCo, dependencies, datasets, or checkpoints. Developer ID signing, notarization, Intel support, and distributable packaging are out of scope.
