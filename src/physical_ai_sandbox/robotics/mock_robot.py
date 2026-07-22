from __future__ import annotations

import time
from typing import Any

import numpy as np

from physical_ai_sandbox.learning.datasets.feature_encoder import ACTION_DIMENSION
from physical_ai_sandbox.robotics.safety import SafetyLayer
from physical_ai_sandbox.robotics.types import (
    RobotCommandResult,
    RobotConnectionState,
    RobotHealth,
    RobotState,
)
from physical_ai_sandbox.types import Observation


class MockRealRobot:
    name = "mock_real_robot"

    def __init__(
        self, *, latency_seconds: float = 0.0, drop_rate: float = 0.0, seed: int = 42
    ) -> None:
        self.latency_seconds = float(latency_seconds)
        self.drop_rate = float(drop_rate)
        self._rng = np.random.default_rng(seed)
        self.safety = SafetyLayer()
        self._connected = False
        self._observation = default_observation()
        self._health = RobotHealth(RobotConnectionState.DISCONNECTED, hardware_connected=False)

    def connect(self) -> None:
        self._connected = True
        self._health = RobotHealth(
            RobotConnectionState.CONNECTED,
            "Mock robot only; no physical hardware connected",
            self.latency_seconds,
            hardware_connected=False,
            real_world_validated=False,
        )

    def disconnect(self) -> None:
        self._connected = False
        self._health = RobotHealth(RobotConnectionState.DISCONNECTED, hardware_connected=False)

    def reset(self, *, seed: int | None = None) -> RobotState:
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self.safety.reset()
        self._observation = default_observation()
        return self.get_state()

    def get_state(self) -> RobotState:
        self._require_connected()
        return RobotState(
            observation=self._observation,
            timestamp=time.time(),
            backend="mock_robot",
            health=self._health,
            metadata={"execution_backend": "mock_robot", "hardware_connected": False},
        )

    def send_action(self, action: np.ndarray) -> RobotCommandResult:
        self._require_connected()
        if self.latency_seconds > 0.0:
            time.sleep(self.latency_seconds)
        if self.drop_rate > 0.0 and self._rng.random() < self.drop_rate:
            self._health = RobotHealth(RobotConnectionState.DEGRADED, "mock_packet_drop")
            return RobotCommandResult(
                np.zeros(ACTION_DIMENSION), False, "mock_packet_drop", self.get_state()
            )
        safety = self.safety.filter_action(action)
        if safety.safe:
            self._observation = update_mock_observation(self._observation, safety.action)
        return RobotCommandResult(safety.action, safety.safe, safety.reason, self.get_state())

    def emergency_stop(self, reason: str = "emergency_stop") -> None:
        self.safety.emergency_stop(reason)
        self._health = RobotHealth(RobotConnectionState.EMERGENCY_STOPPED, reason)

    def health(self) -> RobotHealth:
        return self._health

    def close(self) -> None:
        self.disconnect()

    def metadata(self) -> dict[str, Any]:
        return {
            "execution_backend": "mock_robot",
            "hardware_connected": False,
            "real_world_validated": False,
            "latency_seconds": self.latency_seconds,
            "drop_rate": self.drop_rate,
        }

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("MockRealRobot is not connected")


def default_observation() -> Observation:
    return {
        "joint_positions": [0.0] * 7,
        "joint_velocities": [0.0] * 7,
        "gripper_positions": [0.04, 0.04],
        "cube_position": [0.55, 0.0, 0.43],
        "cube_rotation": [1.0, 0.0, 0.0, 0.0],
        "end_effector_position": [0.45, 0.0, 0.58],
        "is_grasped": False,
        "is_success": False,
        "elapsed_time": 0.0,
    }


def update_mock_observation(observation: Observation, action: np.ndarray) -> Observation:
    updated: Observation = {**observation}
    updated["joint_positions"] = (
        (np.asarray(observation["joint_positions"], dtype=np.float64) + action[:7] * 0.01)
        .astype(float)
        .tolist()
    )
    updated["elapsed_time"] = float(observation["elapsed_time"] + 0.02)
    return updated
