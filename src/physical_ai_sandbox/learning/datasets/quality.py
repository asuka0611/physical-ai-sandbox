from __future__ import annotations

from typing import Any

import numpy as np

from physical_ai_sandbox.learning.datasets.episode_dataset import DatasetArrays, EpisodeRecord


def quality_report(
    episodes: list[EpisodeRecord],
    arrays_by_split: dict[str, DatasetArrays],
    *,
    broken_episodes: dict[str, str] | None = None,
) -> dict[str, Any]:
    total_steps = sum(episode.length for episode in episodes)
    success_count = sum(1 for episode in episodes if episode.is_success)
    lengths = [episode.length for episode in episodes]
    duplicate_episode_ids = sorted(
        episode_id for episode_id in {episode.episode_id for episode in episodes}
        if [episode.episode_id for episode in episodes].count(episode_id) > 1
    )
    report: dict[str, Any] = {
        "episode_count": len(episodes),
        "step_count": total_steps,
        "success_episode_count": success_count,
        "failure_episode_count": len(episodes) - success_count,
        "success_rate": success_count / len(episodes) if episodes else 0.0,
        "min_episode_length": min(lengths) if lengths else 0,
        "max_episode_length": max(lengths) if lengths else 0,
        "empty_episode_count": sum(1 for length in lengths if length == 0),
        "short_episode_count": sum(1 for length in lengths if 0 < length < 3),
        "duplicate_episode_ids": duplicate_episode_ids,
        "broken_episodes": broken_episodes or {},
        "splits": {},
    }
    rewards: list[np.ndarray] = []
    actions: list[np.ndarray] = []
    observations: list[np.ndarray] = []
    for split_name, arrays in arrays_by_split.items():
        report["splits"][split_name] = {
            "sample_count": int(arrays.observations.shape[0]),
            "episode_count": int(len(set(arrays.episode_ids.astype(str).tolist()))),
            "success_samples": int(np.sum(arrays.success)),
            "observation_shape": list(arrays.observations.shape),
            "action_shape": list(arrays.actions.shape),
        }
        if arrays.rewards.size:
            rewards.append(arrays.rewards.astype(float))
            actions.append(arrays.actions.astype(float))
            observations.append(arrays.observations.astype(float))
    if rewards:
        reward_array = np.concatenate(rewards)
        report["reward"] = {
            "min": float(np.min(reward_array)),
            "max": float(np.max(reward_array)),
            "mean": float(np.mean(reward_array)),
            "std": float(np.std(reward_array)),
        }
    if actions:
        action_array = np.concatenate(actions, axis=0)
        out_of_range = np.where((action_array < -1.0) | (action_array > 1.0))
        report["action"] = {
            "min": action_array.min(axis=0).tolist(),
            "max": action_array.max(axis=0).tolist(),
            "out_of_range_count": int(len(out_of_range[0])),
        }
    if observations:
        observation_array = np.concatenate(observations, axis=0)
        mean = observation_array.mean(axis=0)
        std = observation_array.std(axis=0)
        report["observation"] = {
            "mean": mean.tolist(),
            "std": std.tolist(),
            "zero_variance_count": int(np.sum(std < 1e-8)),
            "outlier_count_abs_z_gt_6": _outlier_count(observation_array, mean, std),
        }
    return report


def _outlier_count(array: np.ndarray, mean: np.ndarray, std: np.ndarray) -> int:
    safe_std = np.where(std < 1e-8, 1.0, std)
    z = np.abs((array - mean) / safe_std)
    return int(np.sum(z > 6.0))
