from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.cli.replay_episode import replay_episode
from physical_ai_sandbox.controllers.behavior_cloning import BehaviorCloningController
from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH
from physical_ai_sandbox.types import Observation

ROLLOUT_EVALUATOR_VERSION = "phase3.5.bc_rollout.v1"


@dataclass(frozen=True, slots=True)
class RolloutConfig:
    episodes: int = 3
    max_steps: int = 200
    seed: int = 42
    record: bool = True
    replay: bool = True
    lift_threshold: float = 0.03


class BCRolloutEvaluator:
    def __init__(
        self,
        model_path: str | Path,
        *,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        log_root: str | Path | None = None,
        rollout_config: RolloutConfig | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.config_path = Path(config_path)
        self.log_root = Path(log_root) if log_root is not None else None
        self.rollout_config = rollout_config or RolloutConfig()
        self.controller = BehaviorCloningController(self.model_path)
        self.rng = np.random.default_rng(self.rollout_config.seed)

    def evaluate(self, *, report_path: str | Path | None = None) -> dict[str, Any]:
        if self.rollout_config.episodes <= 0:
            raise ValueError("episodes must be positive")
        if self.rollout_config.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        episode_results = [
            self._run_episode(index) for index in range(self.rollout_config.episodes)
        ]
        report = self._aggregate(episode_results)
        if report_path is not None:
            output = Path(report_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return report

    def _run_episode(self, episode_index: int) -> dict[str, Any]:
        episode_seed = int(self.rollout_config.seed + episode_index)
        # Reserved for future randomized resets while keeping the public seed contract stable.
        _episode_rng = np.random.default_rng(episode_seed)
        env = PandaPickPlaceEnv(config_path=self.config_path, log_root=self.log_root)
        episode_dir: Path | None = None
        observation = env.reset()
        if self.rollout_config.record:
            episode_dir = env.start_recording(
                {
                    "mode": "bc_rollout",
                    "evaluator_version": ROLLOUT_EVALUATOR_VERSION,
                    "model_path": str(self.model_path),
                    "checkpoint_path": str(self.controller.checkpoint_path),
                    "seed": self.rollout_config.seed,
                    "episode_seed": episode_seed,
                    "episode_index": episode_index,
                    "max_steps": self.rollout_config.max_steps,
                },
            )
        total_reward = 0.0
        steps = 0
        terminated = False
        truncated = False
        unsafe_reason: str | None = None
        env_failure_reason: str | None = None
        grasped = bool(observation["is_grasped"])
        lifted = self._is_lifted(env, observation)
        reached_goal = self._reached_goal(env, observation)
        try:
            for _ in range(self.rollout_config.max_steps):
                controller_output = self.controller.act(observation)
                if not controller_output.is_safe:
                    unsafe_reason = controller_output.unsafe_reason or "unsafe_action"
                    break
                observation, reward, terminated, truncated, info = env.step(
                    controller_output.action,
                )
                steps += 1
                total_reward += float(reward)
                grasped = grasped or bool(observation["is_grasped"])
                lifted = lifted or self._is_lifted(env, observation)
                reached_goal = reached_goal or self._reached_goal(env, observation)
                env_failure_reason = info.get("failure_reason")
                if terminated or truncated:
                    break
            failure_reason = self._failure_reason(
                success=bool(observation["is_success"]),
                unsafe_reason=unsafe_reason,
                env_failure_reason=env_failure_reason,
                steps=steps,
                terminated=terminated,
                truncated=truncated,
            )
            result = {
                "episode_index": episode_index,
                "seed": episode_seed,
                "episode_dir": str(episode_dir) if episode_dir is not None else None,
                "steps": steps,
                "total_reward": total_reward,
                "success": bool(observation["is_success"]),
                "terminated": terminated,
                "truncated": truncated,
                "grasped": grasped,
                "lifted": lifted,
                "reached_goal": reached_goal,
                "failure_reason": failure_reason,
                "final_observation": observation,
                "unsafe_reason": unsafe_reason,
            }
        finally:
            if env.recorder.is_recording:
                env.stop_recording(
                    {
                        "mode": "bc_rollout",
                        "success": bool(observation["is_success"]),
                        "steps": steps,
                        "total_reward": total_reward,
                        "unsafe_reason": unsafe_reason,
                    },
                )
            env.close()
        if self.rollout_config.replay and episode_dir is not None:
            result["replay"] = replay_episode(
                episode_dir,
                config_path=self.config_path,
                max_steps=steps,
            )
        else:
            result["replay"] = None
        return result

    def _aggregate(self, episodes: list[dict[str, Any]]) -> dict[str, Any]:
        count = len(episodes)
        failures = Counter(str(item["failure_reason"]) for item in episodes)
        replay_runs = [item["replay"] for item in episodes if item.get("replay") is not None]
        replay_successes = sum(1 for item in replay_runs if item.get("success"))
        warnings = list(self.controller.metadata.get("warnings", []))
        dataset_episode_count = self.controller.metadata.get("dataset_episode_count", "unknown")
        dataset_sample_count = self.controller.metadata.get("dataset_sample_count", "unknown")
        warnings.append(
            f"Closed-loop rollout uses a checkpoint trained from dataset_episode_count="
            f"{dataset_episode_count}, dataset_sample_count={dataset_sample_count}; "
            "record the evaluation conditions and do not treat rates as generalization proof.",
        )
        grasp_lift_success_count = sum(
            1 for item in episodes if item["grasped"] and item["lifted"]
        )
        metrics = {
            "episode_count": count,
            "success_count": sum(1 for item in episodes if item["success"]),
            "success_rate": self._rate(episodes, "success"),
            "average_total_reward": float(np.mean([item["total_reward"] for item in episodes])),
            "average_steps": float(np.mean([item["steps"] for item in episodes])),
            "grasp_rate": self._rate(episodes, "grasped"),
            "lift_rate": self._rate(episodes, "lifted"),
            "grasp_lift_success_count": grasp_lift_success_count,
            "grasp_lift_success_rate": float(grasp_lift_success_count / count),
            "goal_reached_rate": self._rate(episodes, "reached_goal"),
            "replay_count": len(replay_runs),
            "replay_success_count": replay_successes,
        }
        return {
            "created_at": datetime.now(UTC).isoformat(),
            "evaluator_version": ROLLOUT_EVALUATOR_VERSION,
            "model_path": str(self.model_path),
            "checkpoint_path": str(self.controller.checkpoint_path),
            "config_path": str(self.config_path),
            "seed": self.rollout_config.seed,
            "max_steps": self.rollout_config.max_steps,
            "record": self.rollout_config.record,
            "replay": self.rollout_config.replay,
            "metrics": metrics,
            "failure_reasons": dict(sorted(failures.items())),
            "episodes": episodes,
            "warnings": warnings,
            "interpretation": (
                "Closed-loop rollout verifies that the Behavior Cloning checkpoint can be "
                "loaded, normalized with training statistics, clipped, safety-checked, "
                "recorded, and replayed through the Environment API. Interpret rates only "
                "under the recorded dataset size and evaluation conditions."
            ),
        }

    def _failure_reason(
        self,
        *,
        success: bool,
        unsafe_reason: str | None,
        env_failure_reason: str | None,
        steps: int,
        terminated: bool,
        truncated: bool,
    ) -> str:
        if success:
            return "success"
        if unsafe_reason is not None:
            return f"unsafe_controller_output: {unsafe_reason}"
        if env_failure_reason:
            return env_failure_reason
        if truncated:
            return "truncated"
        if terminated:
            return "terminated_without_success"
        if steps >= self.rollout_config.max_steps:
            return "max steps reached"
        return "stopped_before_max_steps"

    def _is_lifted(self, env: PandaPickPlaceEnv, observation: Observation) -> bool:
        cube_z = float(observation["cube_position"][2])
        lift_z = env.evaluator.table_top_z + env.cube_half_size + self.rollout_config.lift_threshold
        return cube_z >= lift_z

    @staticmethod
    def _reached_goal(env: PandaPickPlaceEnv, observation: Observation) -> bool:
        cube_xy = np.asarray(observation["cube_position"][:2], dtype=np.float64)
        target_xy = env.evaluator.target_position[:2]
        return float(np.linalg.norm(cube_xy - target_xy)) <= env.evaluator.target_radius

    @staticmethod
    def _rate(episodes: list[dict[str, Any]], key: str) -> float:
        return float(sum(1 for item in episodes if item[key]) / len(episodes))
