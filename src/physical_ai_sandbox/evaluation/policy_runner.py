from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv
from physical_ai_sandbox.learning.ppo.task import grasp_lift_reward, rollout_metrics, task_success
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH
from physical_ai_sandbox.policies.base import Policy

POLICY_EVALUATOR_VERSION = "phase5.policy_evaluation.v1"


@dataclass(frozen=True, slots=True)
class PolicyEvaluationConfig:
    episodes: int = 3
    max_steps: int = 200
    seed: int = 42
    headless: bool = True
    deterministic: bool = True
    record: bool = False
    config_path: str | Path = DEFAULT_CONFIG_PATH
    log_root: str | Path = "logs/policy_evaluation"
    save_trajectory: bool = True


@dataclass(frozen=True, slots=True)
class EpisodeEvaluationResult:
    episode_number: int
    seed: int
    success: bool
    grasp_lift_success: bool
    pick_place_success: bool
    total_reward: float
    episode_length: int
    completion_time: float
    wall_time_seconds: float
    final_object_height: float
    grasp_achieved: bool
    lift_achieved: bool
    termination_reason: str
    policy_name: str
    model_path: str | None
    timestamp: str
    episode_dir: str | None
    action_trajectory: list[list[float]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_policy(
    policy: Policy,
    *,
    config: PolicyEvaluationConfig | None = None,
    model_path: str | Path | None = None,
    output: str | Path | None = None,
    csv_output: str | Path | None = None,
) -> dict[str, Any]:
    evaluation_config = config or PolicyEvaluationConfig()
    _validate_config(evaluation_config)
    if not evaluation_config.headless:
        raise NotImplementedError("Viewer policy evaluation is planned for Phase 5 UI/replay work")
    started_at = datetime.now(UTC).isoformat()
    episodes = [
        _run_episode(
            policy,
            evaluation_config,
            episode_number=index,
            episode_seed=int(evaluation_config.seed + index),
            model_path=str(model_path) if model_path is not None else None,
        )
        for index in range(evaluation_config.episodes)
    ]
    report = _aggregate(
        policy,
        episodes,
        config=evaluation_config,
        model_path=str(model_path) if model_path is not None else None,
        started_at=started_at,
    )
    if output is not None:
        write_json_report(report, output)
    if csv_output is not None:
        write_episode_csv(episodes, csv_output)
    return report


def write_json_report(report: dict[str, Any], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_episode_csv(episodes: list[EpisodeEvaluationResult], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_csv_row(item) for item in episodes]
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _run_episode(
    policy: Policy,
    config: PolicyEvaluationConfig,
    *,
    episode_number: int,
    episode_seed: int,
    model_path: str | None,
) -> EpisodeEvaluationResult:
    env = PandaPickPlaceEnv(config_path=config.config_path, log_root=config.log_root)
    observation = env.reset()
    policy.reset(seed=episode_seed)
    episode_dir: Path | None = None
    if config.record:
        episode_dir = env.start_recording(
            {
                "mode": "policy_evaluation",
                "evaluator_version": POLICY_EVALUATOR_VERSION,
                "policy_name": policy.name,
                "model_path": model_path,
                "seed": config.seed,
                "episode_seed": episode_seed,
                "episode_number": episode_number,
                "max_steps": config.max_steps,
            },
        )
    total_reward = 0.0
    steps = 0
    unsafe_reason: str | None = None
    env_failure_reason: str | None = None
    grasp_achieved = bool(observation["is_grasped"])
    lift_achieved = False
    grasp_lift_success = False
    action_trajectory: list[list[float]] = []
    wall_start = perf_counter()
    try:
        for _ in range(config.max_steps):
            action = policy.act(observation, deterministic=config.deterministic).clipped()
            if not action.is_safe:
                unsafe_reason = action.unsafe_reason or "unsafe_action"
                break
            if config.save_trajectory:
                action_trajectory.append(action.action.astype(float).tolist())
            observation, _env_reward, terminated, truncated, info = env.step(action.action)
            total_reward += grasp_lift_reward(env, observation)
            steps += 1
            metrics = rollout_metrics(env, observation)
            grasp_achieved = grasp_achieved or metrics["grasped"]
            lift_achieved = lift_achieved or metrics["lifted"]
            grasp_lift_success = grasp_lift_success or metrics["grasp_lift_success"]
            env_failure_reason = info.get("failure_reason")
            if task_success(env, observation):
                grasp_lift_success = True
                break
            if terminated or truncated:
                break
        reason = _termination_reason(
            success=grasp_lift_success,
            unsafe_reason=unsafe_reason,
            env_failure_reason=env_failure_reason,
            steps=steps,
            max_steps=config.max_steps,
        )
        result = EpisodeEvaluationResult(
            episode_number=episode_number,
            seed=episode_seed,
            success=grasp_lift_success,
            grasp_lift_success=grasp_lift_success,
            pick_place_success=bool(observation["is_success"]),
            total_reward=float(total_reward),
            episode_length=steps,
            completion_time=float(observation["elapsed_time"]),
            wall_time_seconds=float(perf_counter() - wall_start),
            final_object_height=float(observation["cube_position"][2]),
            grasp_achieved=grasp_achieved,
            lift_achieved=lift_achieved,
            termination_reason=reason,
            policy_name=policy.name,
            model_path=model_path,
            timestamp=datetime.now(UTC).isoformat(),
            episode_dir=str(episode_dir) if episode_dir is not None else None,
            action_trajectory=action_trajectory,
        )
    finally:
        if env.recorder.is_recording:
            env.stop_recording(
                {
                    "mode": "policy_evaluation",
                    "policy_name": policy.name,
                    "steps": steps,
                    "total_reward": total_reward,
                    "grasp_lift_success": grasp_lift_success,
                    "unsafe_reason": unsafe_reason,
                },
            )
        env.close()
        policy.close()
    return result


def _aggregate(
    policy: Policy,
    episodes: list[EpisodeEvaluationResult],
    *,
    config: PolicyEvaluationConfig,
    model_path: str | None,
    started_at: str,
) -> dict[str, Any]:
    episode_dicts = [item.to_dict() for item in episodes]
    failure_counts = Counter(item.termination_reason for item in episodes)
    rewards = [item.total_reward for item in episodes]
    lengths = [item.episode_length for item in episodes]
    completion_times = [item.completion_time for item in episodes]
    count = len(episodes)
    policy_metadata = policy.metadata()
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "started_at": started_at,
        "evaluator_version": POLICY_EVALUATOR_VERSION,
        "task": "fixed_initial_grasp_lift",
        "policy_name": policy.name,
        "model_path": model_path,
        "config": {
            "episodes": config.episodes,
            "max_steps": config.max_steps,
            "seed": config.seed,
            "headless": config.headless,
            "deterministic": config.deterministic,
            "record": config.record,
            "config_path": str(config.config_path),
            "log_root": str(config.log_root),
            "save_trajectory": config.save_trajectory,
        },
        "metrics": {
            "episode_count": count,
            "success_count": sum(1 for item in episodes if item.success),
            "success_rate": _rate(episodes, "success"),
            "grasp_rate": _rate(episodes, "grasp_achieved"),
            "lift_rate": _rate(episodes, "lift_achieved"),
            "grasp_lift_success_rate": _rate(episodes, "grasp_lift_success"),
            "mean_reward": float(np.mean(rewards)),
            "reward_std": float(np.std(rewards)),
            "mean_episode_length": float(np.mean(lengths)),
            "mean_completion_time": float(np.mean(completion_times)),
        },
        "failure_reasons": dict(sorted(failure_counts.items())),
        "episodes": episode_dicts,
        "policy_metadata": policy_metadata,
        "warnings": [
            "Phase 5 evaluates the fixed-initial-condition grasp+lift task first.",
            "Reported rates depend on recorded seeds, episode count, max steps, "
            "and model path; do not treat them as generalization proof.",
        ],
    }


def _validate_config(config: PolicyEvaluationConfig) -> None:
    if config.episodes <= 0:
        raise ValueError("episodes must be positive")
    if config.max_steps <= 0:
        raise ValueError("max_steps must be positive")


def _termination_reason(
    *,
    success: bool,
    unsafe_reason: str | None,
    env_failure_reason: str | None,
    steps: int,
    max_steps: int,
) -> str:
    if success:
        return "grasp_lift_success"
    if unsafe_reason is not None:
        return f"unsafe_policy_output: {unsafe_reason}"
    if env_failure_reason:
        return env_failure_reason
    if steps >= max_steps:
        return "max steps reached"
    return "stopped_before_max_steps"


def _rate(episodes: list[EpisodeEvaluationResult], attr: str) -> float:
    return float(sum(1 for item in episodes if bool(getattr(item, attr))) / len(episodes))


def _csv_row(result: EpisodeEvaluationResult) -> dict[str, Any]:
    data = result.to_dict()
    data.pop("action_trajectory", None)
    return data
