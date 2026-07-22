# Changelog

## 0.5.9 - 2026-07-22

- Started Phase 5.1-5.9 workspace implementation with a Dock-style Tk UI, centralized InputManager, restart/recovery controls, embedded 3D Viewport, evaluation tab, and Timeline placeholder.
- Replaced the ControlPanel external MuJoCo Viewer window with an offscreen MuJoCo renderer in the `mjpython` simulation process. RGB frames are sent to the Tk workspace and drawn directly inside the central 3D Viewport.
- Added visual-only J1-J7 motor housing geoms and joint label sites while preserving collision, actuator, Observation, and 8D Action contracts.
- Added Phase 6 MVP robotics interfaces: RobotInterface, SimulationRobot, MockRealRobot, and SafetyLayer.
- Added Phase 7 MVP perception interfaces: CameraSource, MockCamera, ObjectPerception, and ObservationBuilder.
- Added tests for input focus, embedded Viewport IPC frame handling, robot safety/interface behavior, perception observation building, joint visual markers, and emergency stop mapping.
- Documented that full replay UI, real robot connection, and real camera perception remain unvalidated future work.

## 0.5.0 - 2026-07-22

- Added Phase 5 shared Policy interface for Random, Manual, Behavior Cloning, and PPO adapters.
- Added headless `evaluate_policy.py` CLI with fixed 8D action contract, action clipping, JSON/CSV outputs, per-episode metrics, and action trajectory capture.
- Added `compare_policies.py` CLI for same-seed Random/BC/PPO comparison with JSON, CSV, and Markdown summaries.
- Added tests for policy adapters, BC/PPO checkpoint loading, seed reproducibility, invalid model paths, evaluation metrics, JSON/CSV saving, comparison aggregation, and unsupported viewer mode.
- Verified BC and PPO checkpoints through the shared Environment API in short fixed-condition grasp+lift smoke evaluations. UI evaluation controls and Viewer replay remain pending.

## 0.4.6 - 2026-07-21

- Replaced the self-contained py2app macOS app plan with a local-only `Physical AI Sandbox Launcher.app`.
- Added a Swift/Cocoa Launcher that starts a user LaunchAgent without opening Terminal.
- Changed the local app startup path to run Tkinter under normal Python and MuJoCo simulation in a separate `mjpython` process.
- Added `multiprocessing.connection` IPC between the operation panel and simulation process.
- Added duplicate `run_control_panel.py` prevention, Japanese failure dialogs, Viewer crash reports, and process-group cleanup.
- Verified Launcher startup, operation panel window, MuJoCo rendering path, keyboard-driven UI updates, duplicate launch prevention, Terminal-free startup, and process cleanup.
- Updated build/clean/run scripts, packaging tests, macOS guides, and Phase 4.6 status for the local Launcher strategy.

## 0.4.5 - 2026-07-21

- Added Phase 4.5 Japanese/English UI translation layer with safe fallback behavior.
- Added Tkinter control panel with thread-safe command queue, state snapshots, recording controls, gripper controls, XYZ-style controls, rotation controls, J1-J7 direct joint controls, command-size slider, and Japanese keyboard help.
- Added `scripts/run_control_panel.py` and `physical-ai-control-panel` entrypoint.
- Added optional `ui` and `robot_visual` config sections with backwards-compatible defaults.
- Refreshed MJCF visuals with modern lab robot colors, visual-only shell covers, joint/link covers, accent rings, cable visual, translucent pick/place/target areas, updated lighting, camera, table, floor grid, cube, and obstacle colors.
- Added tests for i18n, fallback language behavior, UI state and command queue logic, backwards-compatible config defaults, MJCF loading, preserved names, visual-only collision disabling, and environment contract regression.

## 0.4.0 - 2026-07-21

- Added Phase 4 NumPy PPO smoke-training pipeline for the fixed-condition grasp+lift task.
- Added Gaussian Actor/Critic policy, rollout buffer, return and GAE calculation, clipped PPO objective, value loss, entropy term, gradient clipping, checkpoint save/load, resume training, and evaluation reports.
- Added BC checkpoint actor initialization and random initialization modes.
- Added `train_ppo.py`, `evaluate_ppo.py`, and `compare_ppo.py` CLIs plus package entrypoints.
- Added BC-only / random PPO / BC-initialized PPO comparison reporting.
- Added PPO tests for GAE, rollout buffer, checkpoint reload, BC initialization, action clipping, seed reproducibility, and short E2E training/evaluation.
- Verified short BC-initialized PPO smoke training and resume. Results are fixed-condition smoke checks only and are not performance claims.

## 0.3.6 - 2026-07-21

- Added Phase 3.6 fixed-initial-condition grasp+lift data collection.
- Added `collect_grasp_lift_demos.py` CLI and `physical-ai-collect-grasp-lift` entrypoint.
- Collected 30 scripted grasp+lift demonstration Episodes under `logs/grasp_lift_demos`.
- Built `datasets/grasp_lift_v1` with 1800 samples, 30 Episodes, and no broken Episodes.
- Trained `models/bc_grasp_lift_v1` for the simplified grasp+lift task.
- Added `grasp_lift_success_rate` to closed-loop rollout reports.
- Verified the retrained BC checkpoint in fixed-condition rollout: grasp_rate=1.0, lift_rate=1.0, grasp_lift_success_rate=1.0 over 10 Episodes.
- Documented that these are fixed-condition simplified-task results, not full Pick-and-Place or generalization performance claims.

## 0.3.5 - 2026-07-21

- Added Phase 3.5 Behavior Cloning closed-loop rollout evaluation.
- Added `BehaviorCloningController` with checkpoint loading, training-time Observation normalization, 8D Action clipping, and NaN/Inf safe-stop behavior.
- Added headless multi-Episode BC rollout metrics for success, reward, grasp, lift, target reach, replay confirmation, and failure-reason aggregation.
- Added `evaluate_bc_rollout.py` CLI and `rollout_report.json` generation.
- Added tests for controller safety, checkpoint contracts, rollout recording/replay, and seed reproducibility.
- Confirmed the current BC checkpoint runs safely through the Environment API, but the 5-Episode dataset remains too small for performance claims.

## 0.3.0 - 2026-07-21

- Added Phase 3 Behavior Cloning pipeline with a NumPy MLP policy, supervised MSE training, checkpoint save/load, training history, and evaluation reports.
- Added `train_behavior_cloning.py` and `evaluate_behavior_cloning.py` CLIs.
- Trained `models/bc_pick_place_v1` on `datasets/pick_place_v1` as a pipeline smoke test.
- Added explicit warnings that the current 5-Episode dataset and 5-sample test split are too small for performance claims.
- Added tests for policy prediction, checkpoint reload, training artifact creation, evaluation metrics, and data-insufficiency warnings.

## 0.2.0 - 2026-07-21

- Added Phase 2 dataset loading, fixed Observation encoding, Action validation, Episode-level splitting, statistics, quality reporting, manifest generation, and dataset validation.
- Added `build_dataset.py`, `validate_dataset.py`, and `inspect_dataset.py` CLIs.
- Added tests for valid and broken Episode loading, NaN/Inf rejection, fixed dimensions, split reproducibility, leakage prevention, normalization, save/load, and validation failures.
- Built `datasets/pick_place_v1` from real Phase 1 Episode logs: 773 samples from 5 valid Episodes, with 1 broken Episode reported in the quality report.

## 0.1.1 - 2026-07-21

- Tuned the default Panda-style home pose so the gripper starts near the cube for manual pick-and-place.
- Added direct 1-7 joint selection, `[` / `]` joint navigation, clearer manual viewer console events, and macOS `mjpython` guidance.
- Added a pick-and-place demo that verifies grasp, lift, target placement, success detection, episode recording, and Viewer-process cleanup.
- Added tests for manual key handling and the pick-and-place demo.

## 0.1.0 - 2026-07-21

- Added Phase 1 project scaffold with uv, pytest, Ruff, and JSON Schema validation.
- Added MuJoCo MJCF generation for a Panda-style 7-axis arm, gripper, table,
  cube, target region, and YAML-declared obstacles.
- Added fixed Action and Observation APIs.
- Added headless environment stepping, reward, success/failure evaluation,
  reset stability, and finite-state checks.
- Added episode recording to `metadata.json`, `steps.jsonl`, and `summary.json`.
- Added replay support for saved action logs.
- Added manual viewer runner with keyboard control hooks.
