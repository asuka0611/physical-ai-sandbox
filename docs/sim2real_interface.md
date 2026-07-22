# Sim2Real Interface MVP

Phase 6 MVP adds a robot abstraction layer without claiming real hardware support.

## Implemented

- `RobotInterface` protocol.
- `SimulationRobot` adapter around `PandaPickPlaceEnv`.
- `MockRealRobot` with configurable latency/drop behavior.
- `SafetyLayer` for action shape checks, NaN/Inf rejection, clipping, rate limiting, and emergency stop latch.
- Metadata fields that prevent fake real-world claims: `execution_backend`, `hardware_connected`, and `real_world_validated`.

## Not Implemented

- Real robot transport.
- Hardware calibration.
- Real-world validation.
