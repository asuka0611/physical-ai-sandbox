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

## Phase 5 Direction

Phase 5 is planned but not implemented in this change set. The next work item is a shared Policy interface plus headless policy evaluation runner. See `PHASE5_PLAN.md` and `PHASE5_COMPLETION_STATUS.md`.
