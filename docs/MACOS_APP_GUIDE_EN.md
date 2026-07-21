# macOS Launcher Guide EN

## Overview

`Physical AI Sandbox Launcher.app` is not a distributable application. It is a local-only launcher for this Mac's development checkout.

Double-clicking it runs the equivalent of the following command without opening a Terminal window:

```bash
cd "/Users/miyachiasuka/Documents/prog/Physical AI Sandbox"
uv run mjpython scripts/run_control_panel.py
```

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

On first launch, macOS may ask for project-folder access. Select `/Users/miyachiasuka/Documents/prog/Physical AI Sandbox`.

## Logs

```text
~/Library/Logs/Physical AI Sandbox Launcher/
```

Startup failures are shown in a Japanese dialog with the log path.

## Notes

The Launcher does not bundle Python, MuJoCo, dependencies, datasets, or checkpoints. Developer ID signing, notarization, Intel support, and distributable packaging are out of scope.
