# Known Issues

- The Phase 1 robot model is a lightweight Panda-style MJCF chain generated in
  code. It does not use the official Franka mesh assets.
- Grasping uses a deterministic attachment rule when the gripper is closed near
  the cube. This keeps manual collection and headless tests stable, but it is
  not yet a full contact-rich manipulation model.
- Manual viewer behavior depends on local GUI availability. Automated validation
  uses headless execution. In the Codex command-runner environment, direct
  interactive `mjpython` launches can stall in macOS task-policy initialization;
  `scripts/run_pick_place_demo.py --viewer` isolates Viewer startup in a child
  process and confirms cleanup, while true hand-keyed control should be run from
  the user's Terminal with `uv run mjpython scripts/run_manual.py`.
- Joint scales and home pose are conservative defaults and should be tuned
  against a more accurate Panda asset in a later phase.

## Phase 2

- The current dataset is small and generated from Phase 1 smoke/demo Episodes. It is valid for pipeline verification, not for training a useful Behavior Cloning policy yet.
- `logs/episodes/episode_20260721_011727_489842` is missing `summary.json`; Phase 2 detects it as broken and excludes it from `datasets/pick_place_v1`.
- Observation vectors are low-dimensional state features only. Camera/image datasets are intentionally out of scope for Phase 2.

## Phase 3

- `models/bc_pick_place_v1` is a pipeline smoke-test model only. The source dataset has 5 valid Episodes and the test split has only 5 samples, so metrics must not be treated as real robot-control performance.
- The Phase 3 policy is a lightweight NumPy MLP to keep the pipeline dependency-light. PyTorch integration can be added later if larger training runs require it.
- Supervised evaluation measures Action-prediction error on saved dataset splits only. Closed-loop rollout is now available in Phase 3.5, but current rollout rates are safety smoke-test metrics because the dataset is still very small.

## Phase 3.5

- `models/bc_pick_place_v1` can be executed through the Environment API, but the current 3-Episode rollout had success_rate=0.0, grasp_rate=0.0, lift_rate=0.0, and goal_reached_rate=0.0. This is recorded as a data-limited safety check, not a model-performance conclusion.
- The rollout seed is recorded and deterministic for the current non-random reset environment. Future randomized resets should consume the episode seed explicitly.
- Replay confirmation validates the recorded action sequence can be applied again; it does not prove the learned policy will recover from perturbations.
- BC rollout Episodes are stored separately under `logs/bc_rollouts` by the CLI so they do not accidentally contaminate future demonstration datasets built from `logs/episodes`.

## Phase 3.6

- `datasets/grasp_lift_v1` contains 30 fixed-initial-condition scripted Episodes for a simplified grasp+lift task. It improves coverage for the initial BC safety loop but does not cover varied cube poses, randomized robot starts, obstacles, release, or full Pick-and-Place completion.
- `models/bc_grasp_lift_v1` reached grasp_rate=1.0 and lift_rate=1.0 in a 10-Episode fixed-condition rollout, while Pick-and-Place `success_rate` remains 0.0 because the policy does not release/place the cube.
- The repeated fixed-condition demos are intentionally low-diversity. They should not be used as evidence of generalization.

## Phase 4

- Phase 4 PPO is a NumPy smoke implementation for pipeline verification. It is not tuned for sample efficiency or final policy quality.
- Initial PPO training uses the same fixed-initial-condition grasp+lift task as Phase 3.6. It does not cover release/place, randomized starts, obstacles, or full Pick-and-Place success.
- PPO can degrade from the BC-only baseline. All reports must be read with their recorded steps, seed, Episode count, max steps, and initialization mode.
- The current random PPO smoke comparison can succeed under the extremely narrow fixed condition, so it should not be interpreted as evidence that random initialization is generally sufficient.

## Phase 4.5

- The new control panel uses Tkinter to keep dependencies minimal. Visual style is functional rather than a full custom design system.
- XYZ controls are manual action presets mapped onto the existing fixed 8D joint-delta Action contract. They are not inverse kinematics and should not be interpreted as precise Cartesian control.
- GUI verification still depends on local macOS windowing and `mjpython`. Automated tests cover UI state, command mapping, config compatibility, and MJCF physics-safe visual settings; true manual Viewer checks should be run from the user's Terminal.
- The robot is still a lightweight generated Panda-style model, now with visual covers. It does not use official Franka meshes.

## Phase 4.6

- `Physical AI Sandbox Launcher.app` is local-only. It is not self-contained and is not suitable for distribution to another Mac.
- The project path is fixed to `/Users/miyachiasuka/Documents/prog/Physical AI Sandbox`; moving the checkout requires updating `packaging/macos/LocalLauncher.swift` and rebuilding.
- The local environment must already have `uv sync` completed and `uv run mjpython` working.
- Because the project lives under `~/Documents`, the first launch may require selecting the project folder in the macOS folder access dialog.
- MuJoCo Viewer visual confirmation from the Launcher requires completing that first-launch folder access step. Automated tests cover packaging and launcher code paths, not human visual inspection of the Viewer window.
- Developer ID signing, notarization, bundled Python/MuJoCo, Intel support, and public distribution packaging are intentionally out of scope for this local Launcher.
