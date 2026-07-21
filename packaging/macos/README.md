# macOS Local Launcher Packaging

Phase 4.6 builds a local-only startup app:

```text
dist/Physical AI Sandbox Launcher.app
```

This is not a self-contained or distributable macOS application. It is a small
Swift/Cocoa launcher for this Mac that starts the existing local development
control panel command without opening Terminal:

```bash
cd "/Users/miyachiasuka/Documents/prog/Physical AI Sandbox"
uv run mjpython scripts/run_control_panel.py
```

## Build

```bash
bash scripts/clean_macos_build.sh
bash scripts/build_macos_app.sh
```

## Launch

```bash
open -n "dist/Physical AI Sandbox Launcher.app"
```

On first launch, macOS may ask for access to the project folder under
`~/Documents`. Select `/Users/miyachiasuka/Documents/prog/Physical AI Sandbox`.

## Local Requirements

- The project exists at `/Users/miyachiasuka/Documents/prog/Physical AI Sandbox`.
- `uv` is installed and visible from the login shell PATH.
- `uv sync` has already been run.
- `uv run mjpython` works in the project checkout.

## Included Resources

- Swift launcher executable.
- App icon when available.
- Info.plist metadata.

The app does not include Python, MuJoCo, dependencies, datasets, model
checkpoints, logs, or project source files.

## Logs

```text
~/Library/Logs/Physical AI Sandbox Launcher/
```

`latest.log` points to the most recent launch log.

## Distribution

Developer ID signing, notarization, py2app, bundled runtimes, and Intel support
are intentionally not used for this local Launcher.
