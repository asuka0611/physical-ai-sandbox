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
