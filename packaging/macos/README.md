# macOS Local Launcher Packaging

Phase 4.6 builds a local-only startup app:

```text
dist/Physical AI Sandbox Launcher.app
```

This is not a self-contained or distributable macOS application. It is a small
Swift/Cocoa launcher for this Mac that starts the existing local development
control panel without opening Terminal:

```bash
cd "/Users/miyachiasuka/Documents/prog/Physical AI Sandbox"
uv run python scripts/run_control_panel.py
```

The operation panel runs under normal Python/Tkinter. The MuJoCo Viewer and
simulation run in a separate `mjpython` process started by the UI.

## Build

```bash
bash scripts/clean_macos_build.sh
bash scripts/build_macos_app.sh
```

## Launch

```bash
open -n "dist/Physical AI Sandbox Launcher.app"
```

The Launcher writes a LaunchAgent plist under:

```text
~/Library/Application Support/Physical AI Sandbox Launcher/
```

It then bootstraps/kickstarts that LaunchAgent and exits. The LaunchAgent starts
`uv run python scripts/run_control_panel.py` in the local checkout.

## Local Requirements

- The project exists at `/Users/miyachiasuka/Documents/prog/Physical AI Sandbox`.
- `uv` is installed and visible from the login shell PATH.
- `uv sync` has already been run.
- `uv run mjpython` works in the project checkout.

## Logs

```text
~/Library/Logs/Physical AI Sandbox Launcher/
```

`latest.log` points to the most recent launch log.

## Distribution

Developer ID signing, notarization, py2app, bundled runtimes, and Intel support
are intentionally not used for this local Launcher.
