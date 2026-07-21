from __future__ import annotations

import mujoco

from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv


def test_yaml_box_and_cylinder_are_in_model() -> None:
    env = PandaPickPlaceEnv()
    box_id = mujoco.mj_name2id(env.model, mujoco.mjtObj.mjOBJ_BODY, "obstacle_box")
    cylinder_id = mujoco.mj_name2id(env.model, mujoco.mjtObj.mjOBJ_BODY, "obstacle_cylinder")
    assert box_id >= 0
    assert cylinder_id >= 0
    env.close()
