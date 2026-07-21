# Phase 4.6 Completion Status

Last verified: 2026-07-21

## Implemented

- macOS app launcher/runtime modules under `physical_ai_sandbox.app`.
- LaunchServices-safe bundled startup: the `.app` runs control panel/runtime in-process.
- Development launcher path still uses managed subprocess startup and terminate/kill cleanup.
- Application Support path management.
- First-launch config copy.
- Config priority: CLI config, Application Support config, bundled default config.
- Writable directories: `configs`, `logs`, `datasets`, `models`, `replays`, `crash-reports`.
- Crash report writer with app version, phase, macOS version, architecture, Python version, traceback, argv, and config path with home-path masking.
- Japanese error dialog fallback.
- Tkinter menu for app, experiment, view, language, logs, guide, GitHub, and version actions.
- App version display from package metadata or bundled `pyproject.toml`.
- py2app packaging setup.
- Build, clean, and bundled-run scripts.
- Generated app icon and `.icns` build script.
- macOS app documentation in Japanese and English.
- Regression tests for paths, first launch, bundle resource resolution, runtime protocol, process cleanup, shutdown, and packaging hygiene.

## Packaging Strategy

Phase 4.6 uses `py2app`.

The signed `.app` does not spawn a second copy of its own app executable from LaunchServices. Earlier smoke testing found that child-app startup can be killed by macOS with `SIGKILL (Code Signature Invalid)`. The final bundled launcher therefore prepares resources and Application Support, then runs the existing Japanese/English Tkinter control panel and MuJoCo Viewer in the app process. Development launch paths retain managed subprocess cleanup.

## Bundle

Target output:

```text
dist/Physical AI Sandbox.app
```

Bundle Identifier:

```text
com.asuka0611.physicalaisandbox
```

Minimum macOS:

```text
14.0
```

Version:

```text
0.2.0
```

Primary architecture:

```text
Apple Silicon / arm64
```

## Verification Results

- `uv sync`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 73 tests.
- `uv run python scripts/validate_config.py`: passed.
- `uv run python scripts/run_headless.py --steps 1000`: passed; 20 simulated seconds, no crash.
- `bash scripts/build_macos_app.sh`: passed; generated `dist/Physical AI Sandbox.app`.
- `test -d "dist/Physical AI Sandbox.app"`: passed.
- `codesign --verify --deep --strict "dist/Physical AI Sandbox.app"`: passed.
- `spctl --assess --type execute "dist/Physical AI Sandbox.app"`: rejected as expected for Ad Hoc signing without Developer ID notarization.
- Bundle scan for the repository owner home path under `dist/Physical AI Sandbox.app/Contents`: passed, no hardcoded user path found.
- Direct executable `--help` smoke: passed.
- Direct executable runtime smoke with `--role runtime --no-viewer`: launched and stayed alive until terminated.
- Direct executable launcher smoke: launched and stayed alive until terminated.
- `open -n "dist/Physical AI Sandbox.app"` smoke: launched one app process and left no process after SIGTERM.
- App crash-report directory after final smoke: empty.
- App-related process scan after final smoke: no remaining process.

## GUI Manual Check

Automated smoke confirmed `.app` startup, `open` startup, resource loading, crash-report absence, and shutdown cleanup. A full human desktop pass is still recommended for:

- Finder double-click launch.
- Dock/Launchpad launch.
- Japanese UI rendering.
- English switching.
- Viewer camera interaction.
- Manual robot operation.
- Recording start/stop from the GUI.
- Full Pick-and-Place visual behavior.

## Signing

Phase 4.6 uses Ad Hoc signing only:

```bash
codesign --force --deep --sign - "dist/Physical AI Sandbox.app"
```

Developer ID signing, Hardened Runtime, notarization, and stapling are not completed.

## Known Constraints

- Apple Silicon is the primary build target.
- Intel Mac support is not verified.
- Gatekeeper rejection is expected until Developer ID signing and notarization are added.
- The bundle depends on py2app collecting MuJoCo native runtime resources.
- py2app currently collects some optional/test modules, so bundle size is not optimized.
- Full human GUI Pick-and-Place validation remains separate from this packaging smoke pass.
