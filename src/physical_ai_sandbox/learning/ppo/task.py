from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv
from physical_ai_sandbox.types import Observation


@dataclass(frozen=True, slots=True)
class GraspLiftTaskConfig:
    lift_threshold: float = 0.03
    success_bonus: float = 5.0
    grasp_bonus: float = 0.8
    lift_bonus: float = 1.2
    distance_weight: float = 0.2
    height_weight: float = 0.5


def is_lifted(
    env: PandaPickPlaceEnv,
    observation: Observation | dict[str, Any],
    *,
    lift_threshold: float = 0.03,
) -> bool:
    cube_z = float(observation["cube_position"][2])
    lift_z = env.evaluator.table_top_z + env.cube_half_size + lift_threshold
    return cube_z >= lift_z


def task_success(
    env: PandaPickPlaceEnv,
    observation: Observation | dict[str, Any],
    *,
    lift_threshold: float = 0.03,
) -> bool:
    return bool(
        observation["is_grasped"]
        and is_lifted(env, observation, lift_threshold=lift_threshold)
    )


def grasp_lift_reward(
    env: PandaPickPlaceEnv,
    observation: Observation | dict[str, Any],
    *,
    config: GraspLiftTaskConfig | None = None,
) -> float:
    task_config = config or GraspLiftTaskConfig()
    cube = np.asarray(observation["cube_position"], dtype=np.float64)
    ee = np.asarray(observation["end_effector_position"], dtype=np.float64)
    distance = float(np.linalg.norm(ee - cube))
    table_cube_z = env.evaluator.table_top_z + env.cube_half_size
    lifted_height = max(0.0, float(cube[2]) - table_cube_z)
    reward = -task_config.distance_weight * distance + task_config.height_weight * lifted_height
    if observation["is_grasped"]:
        reward += task_config.grasp_bonus
    if is_lifted(env, observation, lift_threshold=task_config.lift_threshold):
        reward += task_config.lift_bonus
    if task_success(env, observation, lift_threshold=task_config.lift_threshold):
        reward += task_config.success_bonus
    if not np.isfinite(reward):
        raise FloatingPointError("grasp_lift_reward produced NaN or Inf")
    return float(reward)


def rollout_metrics(
    env: PandaPickPlaceEnv,
    observation: Observation | dict[str, Any],
    *,
    lift_threshold: float = 0.03,
) -> dict[str, bool]:
    lifted = is_lifted(env, observation, lift_threshold=lift_threshold)
    grasped = bool(observation["is_grasped"])
    return {
        "grasped": grasped,
        "lifted": lifted,
        "grasp_lift_success": bool(grasped and lifted),
    }
