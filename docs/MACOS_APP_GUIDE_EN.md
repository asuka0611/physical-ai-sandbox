# macOS App Guide EN

## Supported Environment

- macOS 14 or later
- Apple Silicon is the primary target
- Intel Macs are not yet verified

## Build

```bash
bash scripts/clean_macos_build.sh
bash scripts/build_macos_app.sh
```

Output:

```text
dist/Physical AI Sandbox.app
```

## Launch

Double-click `dist/Physical AI Sandbox.app` in Finder, or run:

```bash
open "dist/Physical AI Sandbox.app"
```

Or:

```bash
bash scripts/run_bundled_app.sh
```

## First Launch

The app creates:

```text
~/Library/Application Support/Physical AI Sandbox/
```

Main subdirectories:

- `configs/`
- `logs/`
- `datasets/`
- `models/`
- `replays/`
- `crash-reports/`

If `configs/default.yaml` does not exist, the bundled default config is copied there.

## Config

Config resolution order:

1. CLI-provided config
2. `configs/default.yaml` in Application Support
3. Bundled `configs/default.yaml`

## Logs

Runtime logs and recorded Episodes are stored under Application Support. Crash reports are stored in:

```text
~/Library/Application Support/Physical AI Sandbox/crash-reports/
```

## macOS Security Warning

Phase 4.6 uses ad hoc signing only. Gatekeeper may show a warning on first launch.

Developer ID Application signing, Hardened Runtime, notarization, and stapling are required for public distribution.

## Uninstall

Remove the app bundle and optionally remove:

```text
~/Library/Application Support/Physical AI Sandbox/
```

## MuJoCo Constraint

MuJoCo Viewer on macOS normally requires the `mjpython` trampoline. For the distributable `.app`, Phase 4.6 runs the control panel/runtime in the app process to avoid LaunchServices child-app code-signing failures. Development launch scripts still prefer `mjpython` when available.
