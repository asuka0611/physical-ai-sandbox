from __future__ import annotations

from typing import Any, TypedDict

Action = list[float]


class Observation(TypedDict):
    joint_positions: list[float]
    joint_velocities: list[float]
    gripper_positions: list[float]
    cube_position: list[float]
    cube_rotation: list[float]
    end_effector_position: list[float]
    is_grasped: bool
    is_success: bool
    elapsed_time: float


StepResult = tuple[Observation, float, bool, bool, dict[str, Any]]
