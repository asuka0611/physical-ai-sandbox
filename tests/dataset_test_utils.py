from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def observation(step: int = 0) -> dict[str, Any]:
    return {
        "joint_positions": [0.1 * step] * 7,
        "joint_velocities": [0.01 * step] * 7,
        "gripper_positions": [0.04, 0.04],
        "cube_position": [0.55, 0.0, 0.41],
        "cube_rotation": [1.0, 0.0, 0.0, 0.0],
        "end_effector_position": [0.5, 0.0, 0.5],
        "is_grasped": step % 2 == 0,
        "is_success": step > 1,
        "elapsed_time": step * 0.02,
    }


def make_episode(root: Path, episode_id: str, *, success: bool = False, steps: int = 4) -> Path:
    episode_dir = root / episode_id
    episode_dir.mkdir(parents=True)
    (episode_dir / "metadata.json").write_text(
        json.dumps({"episode_id": episode_id, "metadata": {"schema_version": "test"}}) + "\n",
        encoding="utf-8",
    )
    with (episode_dir / "steps.jsonl").open("w", encoding="utf-8") as file:
        for index in range(steps):
            step_success = success and index == steps - 1
            payload = {
                "episode_id": episode_id,
                "step": index,
                "time": index * 0.02,
                "observation": {**observation(index), "is_success": step_success},
                "action": [0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0],
                "reward": float(index),
                "success": step_success,
                "grasp_state": index > 1,
                "info": {"failure_reason": None},
            }
            file.write(json.dumps(payload) + "\n")
    (episode_dir / "summary.json").write_text(
        json.dumps(
            {"episode_id": episode_id, "steps": steps, "summary": {"success": success}},
        )
        + "\n",
        encoding="utf-8",
    )
    return episode_dir
