from __future__ import annotations

import mujoco

from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH
from physical_ai_sandbox.scene.config import apply_config_defaults, load_yaml, validate_config
from physical_ai_sandbox.scene.mjcf import build_panda_pick_place_mjcf

VISUAL_ONLY_GEOMS = [
    "target_region_geom",
    "pick_region_geom",
    "place_region_geom",
    "table_visual_bevel_geom",
    "base_cover_geom",
    "base_accent_ring_geom",
    "link1_cover_geom",
    "link2_cover_geom",
    "link3_cover_geom",
    "link4_cover_geom",
    "link5_cover_geom",
    "link6_cover_geom",
    "link7_cover_geom",
    "hand_cover_geom",
    "left_finger_cover_geom",
    "right_finger_cover_geom",
    "joint1_motor_housing_geom",
    "joint2_motor_housing_geom",
    "joint3_motor_housing_geom",
    "joint4_motor_housing_geom",
    "joint5_motor_housing_geom",
    "joint6_motor_housing_geom",
    "joint7_motor_housing_geom",
]


def test_old_config_shape_receives_ui_defaults() -> None:
    config = load_yaml(DEFAULT_CONFIG_PATH)
    config.pop("ui", None)
    config.pop("robot_visual", None)

    validate_config(config)
    merged = apply_config_defaults(config)

    assert merged["ui"]["language"] == "ja"
    assert merged["ui"]["show_control_panel"] is True
    assert merged["robot_visual"]["theme"] == "modern_lab"


def test_robot_and_scene_visual_mjcf_loads_with_names_preserved() -> None:
    config = apply_config_defaults(load_yaml(DEFAULT_CONFIG_PATH))
    model = mujoco.MjModel.from_xml_string(build_panda_pick_place_mjcf(config))

    for name in [
        "panda_base",
        "panda_link1",
        "panda_link7",
        "panda_hand",
        "cube",
        "target_region",
    ]:
        assert mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name) >= 0
    for name in [f"panda_joint{index}" for index in range(1, 8)]:
        assert mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name) >= 0
    for name in [f"act_joint{index}" for index in range(1, 8)]:
        assert mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, name) >= 0
    assert mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "end_effector") >= 0
    for name in [f"joint{index}_label_site" for index in range(1, 8)]:
        assert mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name) >= 0


def test_visual_only_geoms_have_collision_disabled() -> None:
    config = apply_config_defaults(load_yaml(DEFAULT_CONFIG_PATH))
    model = mujoco.MjModel.from_xml_string(build_panda_pick_place_mjcf(config))

    for name in VISUAL_ONLY_GEOMS:
        geom_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
        assert geom_id >= 0, name
        assert model.geom_contype[geom_id] == 0, name
        assert model.geom_conaffinity[geom_id] == 0, name


def test_visual_refresh_keeps_environment_observation_action_contract() -> None:
    env = PandaPickPlaceEnv()
    try:
        observation, _reward, _terminated, _truncated, info = env.step([0.0] * 8)
    finally:
        env.close()

    assert len(observation["joint_positions"]) == 7
    assert len(observation["gripper_positions"]) == 2
    assert len(info["action_clipped"]) == 8
