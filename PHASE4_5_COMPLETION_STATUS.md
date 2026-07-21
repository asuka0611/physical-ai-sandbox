# Phase 4.5 Completion Status

Last verified: 2026-07-21

## Implemented

- Japanese/English UI translation layer: `physical_ai_sandbox.ui.i18n`.
- Safe translation fallback for unsupported languages and undefined keys.
- Tkinter control panel: `physical_ai_sandbox.ui.control_panel`.
- Thread-safe command queue and state snapshot model.
- Simulation worker thread separated from the Tk UI main thread.
- Control panel launch script: `scripts/run_control_panel.py`.
- Package entrypoint: `physical-ai-control-panel`.
- Runtime controls for start, pause/resume, reset, quit, recording start/stop, gripper open/close, camera reset, XYZ-style commands, rotation commands, J1-J7 direct joint commands, and command-size adjustment.
- Japanese and English keyboard help in the UI.
- Optional config sections: `ui` and `robot_visual`.
- Backwards-compatible defaults for old configs without the new sections.
- Modern lab visual refresh for the generated MJCF scene.

## UI Changes

- The control panel displays run state, Episode, Step, Reward, Grasped, Lifted, Success, Recording, Controller, and the latest event.
- Language can be switched between `ja` and `en` from the panel.
- GUI logic is separated from Tk widgets so command queue and state behavior can be tested headlessly.

## Japanese Scope

- Japanese text is limited to display strings and help text.
- Internal Python identifiers, body names, joint names, actuator names, site names, Observation fields, Action fields, Dataset files, and checkpoint contracts remain English.

## Robot Design Changes

- Off-white visual covers were added to the generated Panda-style arm.
- Dark-gray joint and gripper visuals were added.
- Blue accent rings and a small logo plate were added.
- Cable-like visual geometry was added.
- Added visual geoms use `contype=0`, `conaffinity=0`, and `density=0`.

## Scene Changes

- Dark grid floor material.
- Neutral gray table material with a visual bevel overlay.
- Orange cube material.
- Green translucent target/place area.
- Blue translucent pick area.
- Red obstacle color.
- Updated key/fill lighting and overview camera.

## Physics Compatibility

- Observation and Action specs are unchanged.
- Dataset and checkpoint formats are unchanged.
- Existing body, joint, actuator, and site names are preserved.
- Existing collision geoms remain in place.
- Added visual geoms are collision-disabled and density-zero.

## Verification Commands

- `uv sync`: passed
- `uv run ruff check .`: passed
- `uv run pytest`: passed, 52 tests
- `uv run python scripts/validate_config.py`: passed
- `uv run python scripts/run_headless.py --steps 1000`: passed
- `uv run python scripts/evaluate_bc_rollout.py models/bc_grasp_lift_v1 --episodes 10 --max-steps 200 --seed 42`: passed, grasp_lift_success_rate=1.0, grasp_rate=1.0, lift_rate=1.0, success_rate=0.0

## GUI Manual Check

- `uv run python scripts/run_control_panel.py --help`: passed.
- `uv run mjpython scripts/run_manual.py`: not run in this non-interactive command session.
- `uv run mjpython scripts/run_control_panel.py`: not run in this non-interactive command session.

Manual checks still required from a local Terminal:

- Viewer startup.
- Japanese text rendering.
- Japanese/English runtime switching.
- Start/pause/reset.
- Gripper open/close.
- XYZ operation.
- Viewer process cleanup after exit.
- Visual inspection of refreshed robot and scene.

## Known Constraints

- XYZ controls are action presets mapped to the existing 8D joint-delta contract, not inverse kinematics.
- The visual refresh improves the generated lightweight model but does not add official Franka mesh assets.
- GUI behavior depends on local windowing and `mjpython`; automated coverage focuses on headless UI logic and MJCF contract tests.
