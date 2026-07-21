# macOS Packaging

## Strategy

Phase 4.6 uses `py2app` to build `dist/Physical AI Sandbox.app`.

The app uses a two-process design:

- Launcher process: prepares Application Support, resolves config/resource paths, starts the runtime child, and terminates the child on exit.
- Runtime process: launches the Tkinter Japanese/English control panel and MuJoCo Viewer.

The launcher does not call `mujoco.viewer.launch_passive` directly. The runtime child is started through a bundle-local `Resources/bin/mjpython` wrapper that locates MuJoCo's native `MuJoCo_(mjpython).app/Contents/MacOS/mjpython` trampoline inside the bundled Python resources.

## Build

```bash
bash scripts/clean_macos_build.sh
bash scripts/build_macos_app.sh
```

Output:

```text
dist/Physical AI Sandbox.app
```

## Included Resources

- `physical_ai_sandbox` package
- MuJoCo and native runtime libraries as collected by py2app
- Tkinter dependencies as available from the build Python
- `configs/default.yaml`
- `schemas/scene_config.schema.json`
- UI and macOS app guides
- App icon

## Excluded Data

The build scripts do not copy real datasets, model checkpoints, logs, `.git`, tests, cache directories, or local secrets into the bundle.

## Signing

The build script performs ad hoc signing:

```bash
codesign --force --deep --sign - "dist/Physical AI Sandbox.app"
```

Developer ID signing, Hardened Runtime, notarization, and stapling are not completed in Phase 4.6.
