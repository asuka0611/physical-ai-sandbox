from __future__ import annotations

import numpy as np

from physical_ai_sandbox.learning.datasets.feature_encoder import (
    ACTION_DIMENSION,
    ObservationEncoder,
)
from physical_ai_sandbox.robotics import MockRealRobot, SafetyLayer, SimulationRobot
from physical_ai_sandbox.robotics.types import RobotConnectionState


def test_safety_layer_rejects_invalid_and_nonfinite_actions() -> None:
    safety = SafetyLayer()

    assert safety.filter_action([0.0] * 7).safe is False
    assert safety.filter_action([float("nan")] * ACTION_DIMENSION).reason == "non_finite_action"


def test_safety_layer_clips_rate_limits_and_emergency_stops() -> None:
    safety = SafetyLayer(max_delta=0.2)

    result = safety.filter_action(np.ones(ACTION_DIMENSION))
    assert result.safe is True
    assert np.allclose(result.action, 0.2)
    assert result.reason == "clipped_or_rate_limited"

    safety.emergency_stop("test_stop")
    stopped = safety.filter_action(np.zeros(ACTION_DIMENSION))
    assert stopped.safe is False
    assert stopped.reason == "test_stop"
    assert np.allclose(stopped.action, 0.0)


def test_mock_real_robot_connect_action_and_no_real_claim() -> None:
    robot = MockRealRobot(seed=1)
    robot.connect()

    result = robot.send_action(np.zeros(ACTION_DIMENSION))

    assert result.accepted is True
    assert robot.health().state == RobotConnectionState.CONNECTED
    assert robot.metadata()["hardware_connected"] is False
    assert robot.metadata()["real_world_validated"] is False
    ObservationEncoder().encode(result.state.observation)  # type: ignore[union-attr]


def test_simulation_robot_uses_existing_environment_contract() -> None:
    robot = SimulationRobot()
    robot.connect()
    try:
        state = robot.reset(seed=1)
        result = robot.send_action(np.zeros(ACTION_DIMENSION))
    finally:
        robot.close()

    assert state.backend == "mujoco_sim"
    assert result.accepted is True
    assert result.state is not None
    ObservationEncoder().encode(result.state.observation)
    assert robot.health().state == RobotConnectionState.DISCONNECTED
