from __future__ import annotations

from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from physical_ai_sandbox.evaluation.pick_place import PickPlaceEvaluator
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH
from physical_ai_sandbox.recording.episode_recorder import EpisodeRecorder
from physical_ai_sandbox.scene.config import load_and_validate_config
from physical_ai_sandbox.scene.mjcf import build_panda_pick_place_mjcf
from physical_ai_sandbox.types import Observation, StepResult


class PandaPickPlaceEnv:
    def __init__(
        self,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        *,
        log_root: str | Path | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.config = load_and_validate_config(self.config_path)
        self.xml = build_panda_pick_place_mjcf(self.config)
        self.model = mujoco.MjModel.from_xml_string(self.xml)
        self.data = mujoco.MjData(self.model)
        self.evaluator = PickPlaceEvaluator(self.config)
        self.frame_skip = int(self.config["scene"]["frame_skip"])
        self.joint_delta_scale = float(self.config["scene"]["robot"]["joint_delta_scale"])
        self.home = np.array(self.config["scene"]["robot"]["home"], dtype=float)
        self.gripper_open = float(self.config["scene"]["robot"]["gripper_open"])
        self.gripper_closed = float(self.config["scene"]["robot"]["gripper_closed"])
        self.grasp_distance = float(self.config["scene"]["robot"]["grasp_distance"])
        self.cube_initial_position = np.array(self.config["scene"]["cube"]["position"], dtype=float)
        self.cube_half_size = float(self.config["scene"]["cube"]["size"])
        self.target_joint_positions = self.home.copy()
        self.gripper_target = self.gripper_open
        self.is_grasped = False
        self.is_success = False
        self.elapsed_time = 0.0
        self.last_action = np.zeros(8, dtype=float)
        log_config = self.config["logging"]["root_dir"]
        self.recorder = EpisodeRecorder(log_root or log_config)
        self._cache_ids()
        self.reset()

    def _cache_ids(self) -> None:
        self.arm_joint_ids = [
            mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, f"panda_joint{index}")
            for index in range(1, 8)
        ]
        self.finger_joint_ids = [
            mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "finger_joint1"),
            mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "finger_joint2"),
        ]
        self.cube_joint_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "cube_joint")
        self.cube_body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "cube")
        self.ee_site_id = mujoco.mj_name2id(
            self.model,
            mujoco.mjtObj.mjOBJ_SITE,
            "end_effector",
        )
        self.arm_qpos_addr = np.array(
            [self.model.jnt_qposadr[joint] for joint in self.arm_joint_ids],
        )
        self.arm_qvel_addr = np.array(
            [self.model.jnt_dofadr[joint] for joint in self.arm_joint_ids],
        )
        self.finger_qpos_addr = np.array(
            [self.model.jnt_qposadr[joint] for joint in self.finger_joint_ids],
        )
        self.cube_qpos_addr = int(self.model.jnt_qposadr[self.cube_joint_id])
        self.cube_qvel_addr = int(self.model.jnt_dofadr[self.cube_joint_id])
        self.joint_ranges = self.model.jnt_range[self.arm_joint_ids].copy()

    @property
    def dt(self) -> float:
        return float(self.model.opt.timestep * self.frame_skip)

    def reset(self) -> Observation:
        mujoco.mj_resetData(self.model, self.data)
        self.target_joint_positions = np.clip(
            self.home,
            self.joint_ranges[:, 0],
            self.joint_ranges[:, 1],
        )
        self.gripper_target = self.gripper_open
        self.data.qpos[self.arm_qpos_addr] = self.target_joint_positions
        self.data.qpos[self.finger_qpos_addr] = self.gripper_open
        self.data.qpos[self.cube_qpos_addr : self.cube_qpos_addr + 7] = [
            *self.cube_initial_position,
            1.0,
            0.0,
            0.0,
            0.0,
        ]
        self.data.ctrl[:7] = self.target_joint_positions
        self.data.ctrl[7:9] = self.gripper_open
        self.is_grasped = False
        self.is_success = False
        self.elapsed_time = 0.0
        self.last_action = np.zeros(8, dtype=float)
        self.evaluator.reset()
        mujoco.mj_forward(self.model, self.data)
        return self._observation()

    def step(self, action: list[float] | np.ndarray) -> StepResult:
        clipped_action = self._clip_action(action)
        self.last_action = clipped_action
        joint_delta = clipped_action[:7] * self.joint_delta_scale
        self.target_joint_positions = np.clip(
            self.target_joint_positions + joint_delta,
            self.joint_ranges[:, 0],
            self.joint_ranges[:, 1],
        )
        if clipped_action[7] > 0.1:
            self.gripper_target = self.gripper_closed
        elif clipped_action[7] < -0.1:
            self.gripper_target = self.gripper_open
        self.data.ctrl[:7] = self.target_joint_positions
        self.data.ctrl[7:9] = self.gripper_target
        for _ in range(self.frame_skip):
            mujoco.mj_step(self.model, self.data)
            self._update_grasp_state()
        self.elapsed_time += self.dt
        observation = self._observation()
        cube_speed = float(
            np.linalg.norm(self.data.qvel[self.cube_qvel_addr : self.cube_qvel_addr + 3]),
        )
        self.is_success = self.evaluator.update_success(observation, cube_speed, self.dt)
        observation["is_success"] = self.is_success
        reward = self.evaluator.reward(observation, self.is_success)
        failure_reason = self.evaluator.failure_reason(observation)
        terminated = bool(self.is_success or failure_reason)
        truncated = failure_reason == "time limit exceeded"
        info: dict[str, Any] = {
            "action_clipped": clipped_action.tolist(),
            "failure_reason": failure_reason,
            "stable_time": self.evaluator.state.stable_time,
            "cube_speed": cube_speed,
        }
        if self.recorder.is_recording:
            self.recorder.record_step(
                observation=observation,
                action=clipped_action.tolist(),
                reward=reward,
                time_seconds=self.elapsed_time,
                success=self.is_success,
                grasp_state=self.is_grasped,
                info=info,
            )
        return observation, reward, terminated, truncated, info

    def render(self) -> None:
        mujoco.mj_forward(self.model, self.data)

    def close(self) -> None:
        if self.recorder.is_recording:
            self.stop_recording({"closed": True, "success": self.is_success})

    def start_recording(self, metadata: dict[str, Any] | None = None) -> Path:
        return self.recorder.start(
            {
                "config_path": str(self.config_path),
                "scene": self.config["scene"]["name"],
                **(metadata or {}),
            },
        )

    def stop_recording(self, summary: dict[str, Any] | None = None) -> Path:
        return self.recorder.stop(
            {
                "elapsed_time": self.elapsed_time,
                "success": self.is_success,
                **(summary or {}),
            },
        )

    def _clip_action(self, action: list[float] | np.ndarray) -> np.ndarray:
        array = np.asarray(action, dtype=float)
        if array.shape != (8,):
            raise ValueError(f"Action must have shape (8,), got {array.shape}")
        if not np.all(np.isfinite(array)):
            raise ValueError("Action contains NaN or Inf")
        return np.clip(array, -1.0, 1.0)

    def _update_grasp_state(self) -> None:
        ee_pos = self.data.site_xpos[self.ee_site_id].copy()
        cube_pos = self.data.xpos[self.cube_body_id].copy()
        gripper_closed = self.gripper_target <= self.gripper_closed + 1e-6
        if self.is_grasped and not gripper_closed:
            self.is_grasped = False
            return
        if not self.is_grasped and gripper_closed:
            distance = float(np.linalg.norm(ee_pos - cube_pos))
            if distance <= self.grasp_distance:
                self.is_grasped = True
        if self.is_grasped:
            attached_position = ee_pos + np.array([0.025, 0.0, -0.035])
            min_z = self.evaluator.table_top_z + self.cube_half_size
            attached_position[2] = max(attached_position[2], min_z)
            self.data.qpos[self.cube_qpos_addr : self.cube_qpos_addr + 7] = [
                *attached_position.tolist(),
                1.0,
                0.0,
                0.0,
                0.0,
            ]
            self.data.qvel[self.cube_qvel_addr : self.cube_qvel_addr + 6] = 0.0
            mujoco.mj_forward(self.model, self.data)

    def _observation(self) -> Observation:
        cube_qpos = self.data.qpos[self.cube_qpos_addr : self.cube_qpos_addr + 7].copy()
        observation: Observation = {
            "joint_positions": self.data.qpos[self.arm_qpos_addr].astype(float).tolist(),
            "joint_velocities": self.data.qvel[self.arm_qvel_addr].astype(float).tolist(),
            "gripper_positions": self.data.qpos[self.finger_qpos_addr].astype(float).tolist(),
            "cube_position": cube_qpos[:3].astype(float).tolist(),
            "cube_rotation": cube_qpos[3:7].astype(float).tolist(),
            "end_effector_position": self.data.site_xpos[self.ee_site_id].astype(float).tolist(),
            "is_grasped": bool(self.is_grasped),
            "is_success": bool(self.is_success),
            "elapsed_time": float(self.elapsed_time),
        }
        self._validate_observation(observation)
        return observation

    @staticmethod
    def _validate_observation(observation: Observation) -> None:
        required_lengths = {
            "joint_positions": 7,
            "joint_velocities": 7,
            "gripper_positions": 2,
            "cube_position": 3,
            "cube_rotation": 4,
            "end_effector_position": 3,
        }
        for key, length in required_lengths.items():
            value = observation[key]
            if len(value) != length:
                raise RuntimeError(
                    f"Observation field {key} has length {len(value)}, expected {length}",
                )
            if not np.all(np.isfinite(value)):
                raise RuntimeError(f"Observation field {key} contains NaN or Inf")
