from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH
from physical_ai_sandbox.robotics.safety import SafetyLayer
from physical_ai_sandbox.robotics.types import (
    RobotCommandResult,
    RobotConnectionState,
    RobotHealth,
    RobotState,
)


class SimulationRobot:
    name = "simulation"

    def __init__(self, config_path: str | Path = DEFAULT_CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        self.env: PandaPickPlaceEnv | None = None
        self.safety = SafetyLayer()
        self._health = RobotHealth(RobotConnectionState.DISCONNECTED, hardware_connected=False)
        self._last_observation = None

    def connect(self) -> None:
        if self.env is None:
            self.env = PandaPickPlaceEnv(self.config_path)
        self._health = RobotHealth(
            RobotConnectionState.CONNECTED, backend_message(), hardware_connected=False
        )
        self._last_observation = self.env.reset()

    def disconnect(self) -> None:
        self.close()

    def reset(self, *, seed: int | None = None) -> RobotState:
        del seed
        self._require_connected()
        self.safety.reset()
        self._last_observation = self.env.reset()  # type: ignore[union-attr]
        return self.get_state()

    def get_state(self) -> RobotState:
        self._require_connected()
        observation = self._last_observation or self.env._observation()  # type: ignore[union-attr]
        return RobotState(
            observation=observation,
            timestamp=time.time(),
            backend="mujoco_sim",
            health=self._health,
            metadata={"execution_backend": "mujoco_sim", "hardware_connected": False},
        )

    def send_action(self, action: np.ndarray) -> RobotCommandResult:
        self._require_connected()
        safety = self.safety.filter_action(action)
        if not safety.safe:
            return RobotCommandResult(safety.action, False, safety.reason, self.get_state())
        observation, _reward, _terminated, _truncated, _info = self.env.step(safety.action)  # type: ignore[union-attr]
        self._last_observation = observation
        return RobotCommandResult(safety.action, True, safety.reason, self.get_state())

    def emergency_stop(self, reason: str = "emergency_stop") -> None:
        self.safety.emergency_stop(reason)
        self._health = RobotHealth(
            RobotConnectionState.EMERGENCY_STOPPED, reason, hardware_connected=False
        )

    def health(self) -> RobotHealth:
        return self._health

    def close(self) -> None:
        if self.env is not None:
            self.env.close()
            self.env = None
        self._health = RobotHealth(RobotConnectionState.DISCONNECTED, hardware_connected=False)

    def metadata(self) -> dict[str, Any]:
        return {
            "execution_backend": "mujoco_sim",
            "hardware_connected": False,
            "real_world_validated": False,
            "config_path": str(self.config_path),
        }

    def _require_connected(self) -> None:
        if self.env is None:
            raise RuntimeError("SimulationRobot is not connected")


def backend_message() -> str:
    return "MuJoCo simulation backend; no real hardware connected"
