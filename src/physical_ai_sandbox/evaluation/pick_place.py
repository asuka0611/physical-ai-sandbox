from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from physical_ai_sandbox.types import Observation


@dataclass(slots=True)
class EvaluationState:
    stable_time: float = 0.0
    last_failure_reason: str | None = None


class PickPlaceEvaluator:
    def __init__(self, config: dict[str, Any]) -> None:
        scene = config["scene"]
        self.table_position = np.array(scene["table"]["position"], dtype=float)
        self.table_size = np.array(scene["table"]["size"], dtype=float)
        self.cube_half_size = float(scene["cube"]["size"])
        self.target_position = np.array(scene["target"]["position"], dtype=float)
        self.target_radius = float(scene["target"]["radius"])
        self.time_limit_seconds = float(scene["time_limit_seconds"])
        self.stable_seconds = float(scene["success"]["stable_seconds"])
        self.max_cube_speed = float(scene["success"]["max_cube_speed"])
        self.state = EvaluationState()

    @property
    def table_top_z(self) -> float:
        return float(self.table_position[2] + self.table_size[2])

    def reset(self) -> None:
        self.state = EvaluationState()

    def update_success(self, observation: Observation, cube_speed: float, dt: float) -> bool:
        cube_pos = np.array(observation["cube_position"], dtype=float)
        horizontal_distance = float(np.linalg.norm(cube_pos[:2] - self.target_position[:2]))
        in_target = horizontal_distance <= self.target_radius
        on_table = abs(float(cube_pos[2]) - (self.table_top_z + self.cube_half_size)) <= 0.08
        stable = cube_speed <= self.max_cube_speed
        not_grasped = not observation["is_grasped"]
        if in_target and on_table and stable and not_grasped:
            self.state.stable_time += dt
        else:
            self.state.stable_time = 0.0
        return self.state.stable_time >= self.stable_seconds

    def failure_reason(self, observation: Observation) -> str | None:
        cube_pos = np.array(observation["cube_position"], dtype=float)
        arrays = [
            observation["joint_positions"],
            observation["joint_velocities"],
            observation["gripper_positions"],
            observation["cube_position"],
            observation["cube_rotation"],
            observation["end_effector_position"],
        ]
        if any(not np.all(np.isfinite(array)) for array in arrays):
            return "non-finite observation value"
        if float(cube_pos[2]) < self.table_top_z - 0.20:
            return "cube fell below table"
        if observation["elapsed_time"] >= self.time_limit_seconds:
            return "time limit exceeded"
        return None

    def reward(self, observation: Observation, is_success: bool) -> float:
        cube_pos = np.array(observation["cube_position"], dtype=float)
        ee_pos = np.array(observation["end_effector_position"], dtype=float)
        target_distance = float(np.linalg.norm(cube_pos[:2] - self.target_position[:2]))
        ee_distance = float(np.linalg.norm(ee_pos - cube_pos))
        reward = -target_distance - 0.1 * ee_distance
        if observation["is_grasped"]:
            reward += 0.5
        if cube_pos[2] > self.table_top_z + 0.05:
            reward += 0.2
        if is_success:
            reward += 10.0
        return reward
