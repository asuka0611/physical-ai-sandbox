from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH

LIFT_POSE = np.array([-2.6057, -1.6142, 2.2971, -0.9972, -0.1489, 1.0023, -1.7766])
COLLECTOR_VERSION = "phase3.6.grasp_lift_collection.v1"


@dataclass(frozen=True, slots=True)
class GraspLiftDemoConfig:
    config_path: str | Path = DEFAULT_CONFIG_PATH
    log_root: str | Path = "logs/grasp_lift_demos"
    settle_open_steps: int = 0
    close_steps: int = 15
    max_lift_drive_steps: int = 220
    lift_threshold: float = 0.03


def _drive_to_pose(env: PandaPickPlaceEnv, pose: np.ndarray, *, max_steps: int) -> int:
    steps = 0
    while np.max(np.abs(env.target_joint_positions - pose)) > 0.02 and steps < max_steps:
        delta = np.clip((pose - env.target_joint_positions) / env.joint_delta_scale, -1.0, 1.0)
        action = np.zeros(8, dtype=float)
        action[:7] = delta
        action[7] = 1.0
        env.step(action)
        steps += 1
    return steps


def _is_lifted(env: PandaPickPlaceEnv, *, lift_threshold: float) -> bool:
    observation = env._observation()
    cube_z = float(observation["cube_position"][2])
    lift_z = env.evaluator.table_top_z + env.cube_half_size + lift_threshold
    return cube_z >= lift_z


def run_grasp_lift_demo(
    *,
    record: bool = True,
    episode_index: int = 0,
    seed: int = 42,
    demo_config: GraspLiftDemoConfig | None = None,
) -> dict[str, Any]:
    config = demo_config or GraspLiftDemoConfig()
    env = PandaPickPlaceEnv(config_path=config.config_path, log_root=config.log_root)
    observation = env.reset()
    episode_dir: Path | None = None
    if record:
        episode_dir = env.start_recording(
            {
                "mode": "grasp_lift_demo",
                "collector_version": COLLECTOR_VERSION,
                "task": "fixed_initial_grasp_lift",
                "seed": seed,
                "episode_index": episode_index,
                "fixed_initial_condition": True,
                "lift_pose": LIFT_POSE.tolist(),
            },
        )
    for _ in range(config.settle_open_steps):
        observation, _reward, _terminated, _truncated, _info = env.step([0, 0, 0, 0, 0, 0, 0, -1])
    for _ in range(config.close_steps):
        observation, _reward, _terminated, _truncated, _info = env.step([0, 0, 0, 0, 0, 0, 0, 1])
    grasped_after_close = bool(env.is_grasped)
    drive_steps = _drive_to_pose(env, LIFT_POSE, max_steps=config.max_lift_drive_steps)
    observation = env._observation()
    lifted = _is_lifted(env, lift_threshold=config.lift_threshold)
    task_success = bool(grasped_after_close and lifted and env.is_grasped)
    result: dict[str, Any] = {
        "mode": "grasp_lift_demo",
        "task": "fixed_initial_grasp_lift",
        "seed": seed,
        "episode_index": episode_index,
        "fixed_initial_condition": True,
        "grasped_after_close": grasped_after_close,
        "lifted": lifted,
        "still_grasped_after_lift": bool(env.is_grasped),
        "task_success": task_success,
        "success": task_success,
        "drive_steps": drive_steps,
        "elapsed_time": observation["elapsed_time"],
        "final_cube_position": observation["cube_position"],
        "final_end_effector_position": observation["end_effector_position"],
        "episode_dir": str(episode_dir) if episode_dir is not None else None,
    }
    if record:
        stopped_dir = env.stop_recording(result)
        result["episode_dir"] = str(stopped_dir)
    env.close()
    return result


def collect_grasp_lift_demos(
    *,
    episodes: int = 30,
    log_root: str | Path = "logs/grasp_lift_demos",
    seed: int = 42,
    overwrite: bool = False,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    output = Path(log_root)
    if output.exists() and any(output.iterdir()):
        if not overwrite:
            raise FileExistsError(
                f"Output log_root is not empty: {output}. Use --overwrite or choose another path.",
            )
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    demo_config = GraspLiftDemoConfig(config_path=config_path, log_root=output)
    results = [
        run_grasp_lift_demo(
            record=True,
            episode_index=index,
            seed=seed,
            demo_config=demo_config,
        )
        for index in range(episodes)
    ]
    success_count = sum(1 for item in results if item["task_success"])
    grasp_count = sum(1 for item in results if item["grasped_after_close"])
    lift_count = sum(1 for item in results if item["lifted"])
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "collector_version": COLLECTOR_VERSION,
        "task": "fixed_initial_grasp_lift",
        "config_path": str(config_path),
        "log_root": str(output),
        "seed": seed,
        "fixed_initial_condition": True,
        "episode_count": episodes,
        "task_success_count": success_count,
        "task_success_rate": success_count / episodes,
        "grasp_count": grasp_count,
        "grasp_rate": grasp_count / episodes,
        "lift_count": lift_count,
        "lift_rate": lift_count / episodes,
        "episodes": results,
        "interpretation": (
            "Phase 3.6 collects fixed-initial-condition scripted grasp+lift demos "
            "to improve Behavior Cloning data coverage. These logs are not a "
            "generalization benchmark."
        ),
    }
    (output / "collection_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect fixed-condition grasp+lift demos.")
    parser.add_argument("--episodes", type=int, default=30)
    parser.add_argument("--output", default="logs/grasp_lift_demos")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    report = collect_grasp_lift_demos(
        episodes=args.episodes,
        log_root=args.output,
        seed=args.seed,
        overwrite=args.overwrite,
        config_path=args.config,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
