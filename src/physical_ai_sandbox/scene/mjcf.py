from __future__ import annotations

from html import escape
from typing import Any


def _vec(values: list[float]) -> str:
    return " ".join(f"{float(value):.6g}" for value in values)


def _geom_collision(collision: bool) -> str:
    if collision:
        return ' contype="1" conaffinity="1"'
    return ' contype="0" conaffinity="0"'


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
        f'rgba="0.18 0.35 0.95 1"{collision}/>'
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
    obstacles = "\n".join(_obstacle_xml(obj) for obj in config.get("objects", []))

    return f"""
<mujoco model="physical_ai_sandbox_panda_pick_place">
  <compiler angle="radian" coordinate="local"/>
  <option timestep="{float(scene["timestep"]):.6g}" gravity="0 0 -9.81" integrator="implicitfast"/>
  <visual>
    <global azimuth="135" elevation="-25"/>
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
    <material name="floor_mat" rgba="0.78 0.78 0.74 1"/>
    <material name="table_mat" rgba="0.42 0.34 0.26 1"/>
    <material name="cube_mat" rgba="0.95 0.15 0.12 1"/>
    <material name="target_mat" rgba="0.1 0.8 0.25 0.35"/>
  </asset>
  <worldbody>
    <light name="key" pos="0 -1.2 2.0" dir="0 1 -1" diffuse="0.8 0.8 0.8"/>
    <camera name="overview" pos="1.25 -1.25 1.15" xyaxes="0.70 0.70 0.00 -0.35 0.35 0.87"/>
    <geom name="floor" type="plane" size="2 2 0.02" material="floor_mat"/>
    <body name="table" pos="{_vec(table_pos)}">
      <geom name="table_top" type="box" size="{_vec(table_size)}" material="table_mat"/>
    </body>
    <body name="target_region" pos="{target_pos[0]:.6g} {target_pos[1]:.6g} {target_z:.6g}">
      <geom name="target_region_geom" type="cylinder"
            size="{float(target["radius"]):.6g} 0.002"
            material="target_mat" contype="0" conaffinity="0"/>
    </body>
    {obstacles}
    <body name="panda_base" pos="0 0 0.42">
      <geom name="base_geom" type="cylinder" size="0.09 0.045" rgba="0.18 0.18 0.20 1"/>
      <body name="panda_link1" pos="0 0 0.05">
        <joint name="panda_joint1" type="hinge" axis="0 0 1" range="-2.8973 2.8973"/>
        <geom class="arm" fromto="0 0 0 0 0 0.16"/>
        <body name="panda_link2" pos="0 0 0.16">
          <joint name="panda_joint2" type="hinge" axis="0 1 0" range="-1.7628 1.7628"/>
          <geom class="arm" fromto="0 0 0 0.10 0 0.12"/>
          <body name="panda_link3" pos="0.10 0 0.12">
            <joint name="panda_joint3" type="hinge" axis="0 0 1" range="-2.8973 2.8973"/>
            <geom class="arm" fromto="0 0 0 0.12 0 0"/>
            <body name="panda_link4" pos="0.12 0 0">
              <joint name="panda_joint4" type="hinge" axis="0 1 0" range="-3.0718 -0.0698"/>
              <geom class="arm" fromto="0 0 0 0.10 0 -0.10"/>
              <body name="panda_link5" pos="0.10 0 -0.10">
                <joint name="panda_joint5" type="hinge" axis="0 0 1" range="-2.8973 2.8973"/>
                <geom class="arm" fromto="0 0 0 0.12 0 0"/>
                <body name="panda_link6" pos="0.12 0 0">
                  <joint name="panda_joint6" type="hinge" axis="0 1 0" range="-0.0175 3.7525"/>
                  <geom class="arm" fromto="0 0 0 0.10 0 0"/>
                  <body name="panda_link7" pos="0.10 0 0">
                    <joint name="panda_joint7" type="hinge" axis="0 0 1" range="-2.8973 2.8973"/>
                    <geom class="arm" fromto="0 0 0 0.06 0 0"/>
                    <body name="panda_hand" pos="0.06 0 0">
                      <geom name="hand_geom" type="box" size="0.035 0.045 0.025"
                            rgba="0.12 0.12 0.14 1"/>
                      <site name="end_effector" pos="0.055 0 0" size="0.012" rgba="1 1 0 1"/>
                      <body name="left_finger" pos="0.05 0.025 0">
                        <joint name="finger_joint1" type="slide" axis="0 1 0"
                               range="0 {float(robot["gripper_open"]):.6g}"/>
                        <geom class="finger" name="left_finger_geom"/>
                      </body>
                      <body name="right_finger" pos="0.05 -0.025 0">
                        <joint name="finger_joint2" type="slide" axis="0 -1 0"
                               range="0 {float(robot["gripper_open"]):.6g}"/>
                        <geom class="finger" name="right_finger_geom"/>
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
