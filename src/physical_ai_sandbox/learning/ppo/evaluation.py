from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv
from physical_ai_sandbox.learning.datasets.feature_encoder import ObservationEncoder
from physical_ai_sandbox.learning.ppo.policy import PPOActorCritic
from physical_ai_sandbox.learning.ppo.task import grasp_lift_reward, rollout_metrics, task_success
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH

PPO_EVALUATOR_VERSION = "phase4.ppo_evaluation.v1"


def evaluate_ppo(
    model_dir: str | Path,
    *,
    episodes: int = 5,
    max_steps: int = 120,
    seed: int = 42,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    record: bool = True,
    log_root: str | Path = "logs/ppo_rollouts",
    output: str | Path | None = None,
) -> dict[str, Any]:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    if max_steps <= 0:
        raise ValueError("max_steps must be positive")
    model_path = Path(model_dir)
    checkpoint = model_path / "ppo_checkpoint.npz" if model_path.is_dir() else model_path
    policy, metadata = PPOActorCritic.load(checkpoint)
    encoder = ObservationEncoder()
    mean = np.asarray(metadata["observation_mean"], dtype=np.float64)
    safe_std = np.asarray(metadata["observation_safe_std"], dtype=np.float64)
    rng = np.random.default_rng(seed)
    results = [
        _run_episode(
            policy,
            encoder,
            mean,
            safe_std,
            episode_index=index,
            seed=int(seed + index),
            rng=rng,
            config_path=config_path,
            max_steps=max_steps,
            record=record,
            log_root=log_root,
            model_dir=model_path,
            checkpoint=checkpoint,
        )
        for index in range(episodes)
    ]
    report = _aggregate(results, metadata, model_path, checkpoint, seed, max_steps, record)
    report_path = Path(output) if output is not None else model_path / "evaluation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _run_episode(
    policy: PPOActorCritic,
    encoder: ObservationEncoder,
    mean: np.ndarray,
    safe_std: np.ndarray,
    *,
    episode_index: int,
    seed: int,
    rng: np.random.Generator,
    config_path: str | Path,
    max_steps: int,
    record: bool,
    log_root: str | Path,
    model_dir: Path,
    checkpoint: Path,
) -> dict[str, Any]:
    env = PandaPickPlaceEnv(config_path=config_path, log_root=log_root)
    observation = env.reset()
    episode_dir: Path | None = None
    if record:
        episode_dir = env.start_recording(
            {
                "mode": "ppo_rollout",
                "evaluator_version": PPO_EVALUATOR_VERSION,
                "task": "fixed_initial_grasp_lift",
                "model_dir": str(model_dir),
                "checkpoint": str(checkpoint),
                "seed": seed,
                "episode_index": episode_index,
                "max_steps": max_steps,
            },
        )
    total_reward = 0.0
    steps = 0
    unsafe_reason: str | None = None
    failure_reason: str | None = None
    grasped = False
    lifted = False
    grasp_lift_success = False
    try:
        for _ in range(max_steps):
            normalized = (encoder.encode(observation) - mean) / safe_std
            if not np.all(np.isfinite(normalized)):
                unsafe_reason = "non_finite_normalized_observation"
                break
            try:
                action, _log_prob, _value = policy.sample_action(
                    normalized,
                    rng,
                    deterministic=True,
                )
            except FloatingPointError as error:
                unsafe_reason = str(error)
                break
            observation, _env_reward, terminated, truncated, info = env.step(action)
            reward = grasp_lift_reward(env, observation)
            total_reward += reward
            steps += 1
            metrics = rollout_metrics(env, observation)
            grasped = grasped or metrics["grasped"]
            lifted = lifted or metrics["lifted"]
            grasp_lift_success = grasp_lift_success or metrics["grasp_lift_success"]
            failure_reason = info.get("failure_reason")
            if task_success(env, observation) or terminated or truncated:
                break
        if grasp_lift_success:
            reason = "grasp_lift_success"
        elif unsafe_reason is not None:
            reason = f"unsafe_controller_output: {unsafe_reason}"
        elif failure_reason:
            reason = failure_reason
        elif steps >= max_steps:
            reason = "max steps reached"
        else:
            reason = "stopped_before_max_steps"
        result = {
            "episode_index": episode_index,
            "seed": seed,
            "episode_dir": str(episode_dir) if episode_dir is not None else None,
            "steps": steps,
            "total_reward": total_reward,
            "grasped": grasped,
            "lifted": lifted,
            "grasp_lift_success": grasp_lift_success,
            "pick_place_success": bool(observation["is_success"]),
            "failure_reason": reason,
            "unsafe_reason": unsafe_reason,
            "final_observation": observation,
        }
    finally:
        if env.recorder.is_recording:
            env.stop_recording(
                {
                    "mode": "ppo_rollout",
                    "task": "fixed_initial_grasp_lift",
                    "steps": steps,
                    "total_reward": total_reward,
                    "grasp_lift_success": grasp_lift_success,
                    "unsafe_reason": unsafe_reason,
                },
            )
        env.close()
    return result


def _aggregate(
    episodes: list[dict[str, Any]],
    metadata: dict[str, Any],
    model_dir: Path,
    checkpoint: Path,
    seed: int,
    max_steps: int,
    record: bool,
) -> dict[str, Any]:
    count = len(episodes)
    failures = Counter(str(item["failure_reason"]) for item in episodes)
    warnings = list(metadata.get("warnings", []))
    warnings.append(
        "Phase 4 PPO evaluation is fixed-initial-condition grasp+lift only; PPO can "
        "degrade from the BC-only baseline and results are not generalization proof.",
    )
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "evaluator_version": PPO_EVALUATOR_VERSION,
        "model_dir": str(model_dir),
        "checkpoint": str(checkpoint),
        "task": "fixed_initial_grasp_lift",
        "init": metadata.get("init"),
        "seed": seed,
        "max_steps": max_steps,
        "record": record,
        "metrics": {
            "episode_count": count,
            "average_steps": float(np.mean([item["steps"] for item in episodes])),
            "average_total_reward": float(np.mean([item["total_reward"] for item in episodes])),
            "grasp_rate": _rate(episodes, "grasped"),
            "lift_rate": _rate(episodes, "lifted"),
            "grasp_lift_success_count": sum(1 for item in episodes if item["grasp_lift_success"]),
            "grasp_lift_success_rate": _rate(episodes, "grasp_lift_success"),
            "pick_place_success_rate": _rate(episodes, "pick_place_success"),
        },
        "failure_reasons": dict(sorted(failures.items())),
        "episodes": episodes,
        "metadata_summary": {
            "trainer_version": metadata.get("trainer_version"),
            "trained_steps": metadata.get("trained_steps"),
            "dataset_episode_count": metadata.get("dataset_episode_count"),
            "dataset_sample_count": metadata.get("dataset_sample_count"),
            "init": metadata.get("init"),
        },
        "warnings": warnings,
        "interpretation": (
            "This report checks PPO checkpoint reload and deterministic execution through "
            "the Environment API for the fixed grasp+lift task. Do not interpret it as "
            "full Pick-and-Place performance."
        ),
    }


def _rate(episodes: list[dict[str, Any]], key: str) -> float:
    return float(sum(1 for item in episodes if item[key]) / len(episodes))
