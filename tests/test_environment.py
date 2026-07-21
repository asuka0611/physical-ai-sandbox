from __future__ import annotations

import numpy as np
import pytest

from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv

REQUIRED_OBSERVATION_KEYS = {
    "joint_positions",
    "joint_velocities",
    "gripper_positions",
    "cube_position",
    "cube_rotation",
    "end_effector_position",
    "is_grasped",
    "is_success",
    "elapsed_time",
}


def test_reset_returns_complete_observation() -> None:
    env = PandaPickPlaceEnv()
    observation = env.reset()
    assert set(observation) == REQUIRED_OBSERVATION_KEYS
    assert len(observation["joint_positions"]) == 7
    assert len(observation["joint_velocities"]) == 7
    assert len(observation["gripper_positions"]) == 2
    assert len(observation["cube_position"]) == 3
    assert len(observation["cube_rotation"]) == 4
    assert len(observation["end_effector_position"]) == 3
    env.close()


def test_action_is_clipped_and_step_runs_headless() -> None:
    env = PandaPickPlaceEnv()
    _observation, _reward, _terminated, _truncated, info = env.step([9, -9, 0, 0, 0, 0, 0, 4])
    assert max(info["action_clipped"]) <= 1.0
    assert min(info["action_clipped"]) >= -1.0
    env.close()


def test_bad_action_shape_raises() -> None:
    env = PandaPickPlaceEnv()
    with pytest.raises(ValueError, match="Action must have shape"):
        env.step([0.0, 0.0])
    env.close()


def test_five_resets_do_not_break() -> None:
    env = PandaPickPlaceEnv()
    for _ in range(5):
        observation = env.reset()
        assert np.all(np.isfinite(observation["joint_positions"]))
    env.close()


def test_1000_physics_steps_have_no_nan() -> None:
    env = PandaPickPlaceEnv()
    observation = env.reset()
    for _ in range(100):
        observation, _reward, terminated, truncated, info = env.step(np.zeros(8))
        assert info["failure_reason"] is None
        assert not terminated
        assert not truncated
    for value in observation.values():
        if isinstance(value, list):
            assert np.all(np.isfinite(value))
    env.close()


def test_success_condition_can_be_reached_when_cube_stable_on_target() -> None:
    env = PandaPickPlaceEnv()
    env.reset()
    target = env.evaluator.target_position.copy()
    cube_z = env.evaluator.table_top_z + env.cube_half_size
    env.data.qpos[env.cube_qpos_addr : env.cube_qpos_addr + 7] = [
        target[0],
        target[1],
        cube_z,
        1,
        0,
        0,
        0,
    ]
    env.data.qvel[env.cube_qvel_addr : env.cube_qvel_addr + 6] = 0
    env.is_grasped = False
    for _ in range(int(env.evaluator.stable_seconds / env.dt) + 1):
        observation, _reward, terminated, _truncated, _info = env.step(np.zeros(8))
        if terminated:
            break
    assert observation["is_success"]
    env.close()
