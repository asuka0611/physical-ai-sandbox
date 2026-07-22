from __future__ import annotations

from html import escape
from typing import Any


def _vec(values: list[float]) -> str:
    return " ".join(f"{float(value):.6g}" for value in values)


def _geom_collision(collision: bool) -> str:
    if collision:
        return ' contype="1" conaffinity="1"'
    return _visual_geom_attrs()


def _visual_geom_attrs() -> str:
    return ' contype="0" conaffinity="0" density="0" group="1"'


def _obstacle_xml(obj: dict[str, Any]) -> str:
    name = escape(obj["id"])
    position = _vec(obj["position"])
    collision = _geom_collision(bool(obj["collision"]))
    if obj["type"] == "box":
        half_size = [float(value) * 0.5 for value in obj["size"]]
        return (
            f'<body name="{name}" pos="{position}">'
            f'<geom name="{name}_geom" type="box" size="{_vec(half_size)}" '
            f'rgba="0.85 0.22 0.16 1"{collision}/>'
            "</body>"
        )

    radius = float(obj["radius"])
    half_height = float(obj["height"]) * 0.5
    return (
        f'<body name="{name}" pos="{position}">'
        f'<geom name="{name}_geom" type="cylinder" size="{radius:.6g} {half_height:.6g}" '
        f'rgba="0.85 0.18 0.16 1"{collision}/>'
        "</body>"
    )


def build_panda_pick_place_mjcf(config: dict[str, Any]) -> str:
    scene = config["scene"]
    table = scene["table"]
    cube = scene["cube"]
    target = scene["target"]
    robot = scene["robot"]
    target_pos = target["position"]
    table_pos = table["position"]
    table_size = table["size"]
    cube_size = float(cube["size"])
    target_z = table_pos[2] + table_size[2] + 0.002
    pick_z = table_pos[2] + table_size[2] + 0.003
    visual_attrs = _visual_geom_attrs()
    obstacles = "\n".join(_obstacle_xml(obj) for obj in config.get("objects", []))

    return f"""
<mujoco model="physical_ai_sandbox_panda_pick_place">
  <compiler angle="radian" coordinate="local"/>
  <option timestep="{float(scene["timestep"]):.6g}" gravity="0 0 -9.81" integrator="implicitfast"/>
  <visual>
    <global azimuth="135" elevation="-25" offwidth="1280" offheight="960"/>
    <quality shadowsize="2048"/>
    <headlight diffuse="0.35 0.35 0.35" ambient="0.18 0.18 0.20" specular="0.12 0.12 0.12"/>
    <rgba haze="0.05 0.06 0.07 1"/>
  </visual>
  <default>
    <joint damping="1.2" armature="0.03" limited="true"/>
    <geom friction="0.9 0.04 0.01" solref="0.01 1" solimp="0.9 0.95 0.001"/>
    <default class="arm">
      <geom type="capsule" size="0.035" rgba="0.82 0.84 0.86 1" contype="1" conaffinity="1"/>
    </default>
    <default class="finger">
      <geom type="box" size="0.012 0.008 0.045" rgba="0.12 0.12 0.14 1"/>
    </default>
  </default>
  <asset>
    <texture name="floor_grid" type="2d" builtin="checker" width="512" height="512"
             rgb1="0.12 0.13 0.15" rgb2="0.17 0.18 0.20"/>
    <material name="floor_mat" texture="floor_grid" texrepeat="9 9" reflectance="0.08"/>
    <material name="table_mat" rgba="0.46 0.48 0.50 1" specular="0.25" shininess="0.35"/>
    <material name="cube_mat" rgba="1.0 0.48 0.12 1" specular="0.2"/>
    <material name="target_mat" rgba="0.1 0.85 0.35 0.32"/>
    <material name="pick_mat" rgba="0.16 0.45 0.95 0.20"/>
    <material name="obstacle_mat" rgba="0.85 0.18 0.16 1"/>
    <material name="robot_shell_mat" rgba="0.92 0.91 0.86 1" specular="0.38" shininess="0.55"/>
    <material name="joint_mat" rgba="0.12 0.13 0.15 1" specular="0.25"/>
    <material name="accent_blue_mat" rgba="0.10 0.38 0.95 1" emission="0.02"/>
    <material name="gripper_mat" rgba="0.08 0.09 0.11 1"/>
    <material name="cable_mat" rgba="0.03 0.04 0.05 1"/>
  </asset>
  <worldbody>
    <light name="key" pos="0.15 -1.25 2.25" dir="-0.2 0.8 -1" diffuse="0.95 0.95 0.92"/>
    <light name="fill" pos="-1.1 0.8 1.4" dir="0.6 -0.35 -0.8" diffuse="0.32 0.38 0.46"/>
    <camera name="overview" pos="1.35 -1.35 1.05" xyaxes="0.70 0.70 0.00 -0.33 0.33 0.88"/>
    <geom name="floor" type="plane" size="2.4 2.4 0.02" material="floor_mat"/>
    <body name="table" pos="{_vec(table_pos)}">
      <geom name="table_top" type="box" size="{_vec(table_size)}" material="table_mat"/>
      <geom name="table_visual_bevel_geom" type="box"
            pos="0 0 {table_size[2] + 0.001:.6g}"
            size="{table_size[0] * 0.98:.6g} {table_size[1] * 0.98:.6g} 0.003"
            material="robot_shell_mat"{visual_attrs}/>
    </body>
    <body name="pick_region" pos="{cube["position"][0]:.6g} {cube["position"][1]:.6g} {pick_z:.6g}">
      <geom name="pick_region_geom" type="cylinder" size="0.055 0.0015"
            material="pick_mat"{visual_attrs}/>
    </body>
    <body name="place_region" pos="{target_pos[0]:.6g} {target_pos[1]:.6g} {target_z + 0.001:.6g}">
      <geom name="place_region_geom" type="cylinder"
            size="{float(target["radius"]):.6g} 0.0015"
            material="target_mat"{visual_attrs}/>
    </body>
    <body name="target_region" pos="{target_pos[0]:.6g} {target_pos[1]:.6g} {target_z:.6g}">
      <geom name="target_region_geom" type="cylinder"
            size="{float(target["radius"]):.6g} 0.002"
            material="target_mat"{visual_attrs}/>
    </body>
    {obstacles}
    <body name="panda_base" pos="0 0 0.42">
      <geom name="base_geom" type="cylinder" size="0.09 0.045" rgba="0.18 0.18 0.20 1"/>
      <geom name="base_cover_geom" type="cylinder" size="0.105 0.038"
            pos="0 0 0.006" material="robot_shell_mat"{visual_attrs}/>
      <geom name="base_accent_ring_geom" type="cylinder" size="0.108 0.004"
            pos="0 0 0.047" material="accent_blue_mat"{visual_attrs}/>
      <body name="panda_link1" pos="0 0 0.05">
        <joint name="panda_joint1" type="hinge" axis="0 0 1" range="-2.8973 2.8973"/>
        <geom class="arm" fromto="0 0 0 0 0 0.16"/>
        <geom name="link1_cover_geom" type="capsule" fromto="0 0 0.012 0 0 0.15"
              size="0.047" material="robot_shell_mat"{visual_attrs}/>
        <geom name="joint1_cover_geom" type="cylinder" size="0.055 0.012"
              pos="0 0 0.02" material="joint_mat"{visual_attrs}/>
        <body name="panda_link2" pos="0 0 0.16">
          <joint name="panda_joint2" type="hinge" axis="0 1 0" range="-1.7628 1.7628"/>
          <geom class="arm" fromto="0 0 0 0.10 0 0.12"/>
          <geom name="link2_cover_geom" type="capsule" fromto="0.008 0 0.008 0.092 0 0.112"
                size="0.045" material="robot_shell_mat"{visual_attrs}/>
          <geom name="joint2_accent_geom" type="cylinder" size="0.052 0.006"
                pos="0.012 0 0.012" material="accent_blue_mat"{visual_attrs}/>
          <body name="panda_link3" pos="0.10 0 0.12">
            <joint name="panda_joint3" type="hinge" axis="0 0 1" range="-2.8973 2.8973"/>
            <geom class="arm" fromto="0 0 0 0.12 0 0"/>
            <geom name="link3_cover_geom" type="capsule" fromto="0.01 0 0 0.11 0 0"
                  size="0.043" material="robot_shell_mat"{visual_attrs}/>
            <body name="panda_link4" pos="0.12 0 0">
              <joint name="panda_joint4" type="hinge" axis="0 1 0" range="-3.0718 -0.0698"/>
              <geom class="arm" fromto="0 0 0 0.10 0 -0.10"/>
              <geom name="link4_cover_geom" type="capsule" fromto="0.008 0 -0.008 0.092 0 -0.092"
                    size="0.041" material="robot_shell_mat"{visual_attrs}/>
              <geom name="upper_cable_visual_geom" type="capsule"
                    fromto="0 -0.036 0 0.09 -0.036 -0.085"
                    size="0.0045" material="cable_mat"{visual_attrs}/>
              <body name="panda_link5" pos="0.10 0 -0.10">
                <joint name="panda_joint5" type="hinge" axis="0 0 1" range="-2.8973 2.8973"/>
                <geom class="arm" fromto="0 0 0 0.12 0 0"/>
                <geom name="link5_cover_geom" type="capsule" fromto="0.01 0 0 0.11 0 0"
                      size="0.039" material="robot_shell_mat"{visual_attrs}/>
                <body name="panda_link6" pos="0.12 0 0">
                  <joint name="panda_joint6" type="hinge" axis="0 1 0" range="-0.0175 3.7525"/>
                  <geom class="arm" fromto="0 0 0 0.10 0 0"/>
                  <geom name="link6_cover_geom" type="capsule" fromto="0.008 0 0 0.092 0 0"
                        size="0.037" material="robot_shell_mat"{visual_attrs}/>
                  <body name="panda_link7" pos="0.10 0 0">
                    <joint name="panda_joint7" type="hinge" axis="0 0 1" range="-2.8973 2.8973"/>
                    <geom class="arm" fromto="0 0 0 0.06 0 0"/>
                    <geom name="link7_cover_geom" type="capsule" fromto="0.006 0 0 0.054 0 0"
                          size="0.034" material="robot_shell_mat"{visual_attrs}/>
                    <geom name="wrist_accent_ring_geom" type="cylinder" size="0.037 0.004"
                          pos="0.052 0 0" material="accent_blue_mat"{visual_attrs}/>
                    <body name="panda_hand" pos="0.06 0 0">
                      <geom name="hand_geom" type="box" size="0.035 0.045 0.025"
                            rgba="0.12 0.12 0.14 1"/>
                      <geom name="hand_cover_geom" type="box" size="0.038 0.048 0.028"
                            material="gripper_mat"{visual_attrs}/>
                      <geom name="logo_plate_geom" type="box" pos="0.004 0 0.030"
                            size="0.018 0.030 0.002" material="accent_blue_mat"{visual_attrs}/>
                      <site name="end_effector" pos="0.055 0 0" size="0.012" rgba="1 1 0 1"/>
                      <body name="left_finger" pos="0.05 0.025 0">
                        <joint name="finger_joint1" type="slide" axis="0 1 0"
                               range="0 {float(robot["gripper_open"]):.6g}"/>
                        <geom class="finger" name="left_finger_geom"/>
                        <geom name="left_finger_cover_geom" type="box" size="0.014 0.010 0.047"
                              material="gripper_mat"{visual_attrs}/>
                      </body>
                      <body name="right_finger" pos="0.05 -0.025 0">
                        <joint name="finger_joint2" type="slide" axis="0 -1 0"
                               range="0 {float(robot["gripper_open"]):.6g}"/>
                        <geom class="finger" name="right_finger_geom"/>
                        <geom name="right_finger_cover_geom" type="box" size="0.014 0.010 0.047"
                              material="gripper_mat"{visual_attrs}/>
                      </body>
                    </body>
                  </body>
                </body>
              </body>
            </body>
          </body>
        </body>
      </body>
    </body>
    <body name="cube" pos="{_vec(cube["position"])}">
      <freejoint name="cube_joint"/>
      <geom name="cube_geom" type="box" size="{cube_size:.6g} {cube_size:.6g} {cube_size:.6g}"
            mass="{float(cube["mass"]):.6g}" material="cube_mat"/>
    </body>
  </worldbody>
  <actuator>
    <position name="act_joint1" joint="panda_joint1" kp="75"/>
    <position name="act_joint2" joint="panda_joint2" kp="75"/>
    <position name="act_joint3" joint="panda_joint3" kp="75"/>
    <position name="act_joint4" joint="panda_joint4" kp="75"/>
    <position name="act_joint5" joint="panda_joint5" kp="50"/>
    <position name="act_joint6" joint="panda_joint6" kp="50"/>
    <position name="act_joint7" joint="panda_joint7" kp="35"/>
    <position name="act_finger1" joint="finger_joint1" kp="40"/>
    <position name="act_finger2" joint="finger_joint2" kp="40"/>
  </actuator>
</mujoco>
""".strip()
