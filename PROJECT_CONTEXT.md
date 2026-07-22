# Project Context

Physical AI Sandbox is a shared experimental base for robot simulation, manual
operation, data collection, replay, imitation learning, reinforcement learning,
evaluation, and future real-robot deployment.

Phase 1 is limited to manual operation and simulation foundations:

- MuJoCo environment.
- Panda-style 7-axis robot arm with two-finger gripper.
- Pick-and-place scene.
- Fixed Action and Observation contracts.
- Episode logging and replay.
- Headless execution.
- YAML-configurable obstacles.

Phase 1 must not add AI training. Behavior Cloning, PPO, robot registries,
randomized environments, drones, and real-robot adapters are future phases.

## Phase 4.6 Update

Phase 4.6 now uses a local-only `Physical AI Sandbox Launcher.app`. It launches the existing local development environment through a user LaunchAgent, keeps Tkinter under normal Python, and runs MuJoCo Viewer in a separate `mjpython` simulation process. The app is not distributable and does not bundle Python, MuJoCo, datasets, or checkpoints.

## Phase 5 Update

Phase 5 now has a headless policy evaluation foundation: shared Policy adapters for Random, Manual, BC, and PPO; `evaluate_policy.py`; `compare_policies.py`; JSON/CSV/Markdown outputs; and short real BC/PPO smoke evaluations. This remains fixed-initial-condition grasp+lift only. UI evaluation controls and Viewer replay are still pending. See `docs/policy_evaluation.md` and `PHASE5_COMPLETION_STATUS.md`.

## Phase 5.1-5.9 / Phase 6-7 MVP Update

The app now prioritizes UI/UX and recovery: workspace-style Tk layout, centralized input focus handling, restart controls, background evaluation launch, Viewer window management controls, and robot joint visual markers. Full embedded rendering and complete replay controls are intentionally not claimed complete.

Phase 6 and 7 are MVP foundations only: Simulation/Mock robot interfaces with safety filtering, plus MockCamera and ObservationBuilder with provenance metadata. Real robot and real camera support are not implemented or validated.
