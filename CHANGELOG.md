# Changelog

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
