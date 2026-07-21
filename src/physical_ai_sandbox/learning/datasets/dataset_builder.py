from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.learning.datasets.episode_dataset import DatasetArrays, EpisodeRecord
from physical_ai_sandbox.learning.datasets.episode_loader import EpisodeLoader
from physical_ai_sandbox.learning.datasets.feature_encoder import (
    ObservationEncoder,
    validate_action,
)
from physical_ai_sandbox.learning.datasets.manifest import build_manifest
from physical_ai_sandbox.learning.datasets.normalization import compute_statistics
from physical_ai_sandbox.learning.datasets.quality import quality_report
from physical_ai_sandbox.learning.datasets.splitting import DatasetSplit, split_episodes


@dataclass(frozen=True, slots=True)
class DatasetBuildResult:
    output_dir: Path
    manifest: dict[str, Any]
    statistics: dict[str, Any]
    quality_report: dict[str, Any]


class DatasetBuilder:
    def __init__(
        self,
        *,
        seed: int = 42,
        split_ratio: tuple[float, float, float] = (0.8, 0.1, 0.1),
    ) -> None:
        self.seed = seed
        self.split_ratio = split_ratio
        self.encoder = ObservationEncoder()
        self.loader = EpisodeLoader()

    def build_from_episodes(
        self,
        episodes_root: str | Path,
        output_dir: str | Path,
        *,
        dataset_name: str = "pick_place",
        dataset_version: str = "v1",
        allow_broken: bool = True,
        overwrite: bool = True,
    ) -> DatasetBuildResult:
        scan = self.loader.scan(episodes_root)
        if scan.errors and not allow_broken:
            messages = "\n".join(
                f"{episode_id}: {error}" for episode_id, error in scan.errors.items()
            )
            raise ValueError(f"Broken episodes detected:\n{messages}")
        if not scan.episodes:
            raise ValueError(f"No valid episodes found under {episodes_root}")
        split = split_episodes(scan.episodes, seed=self.seed, ratios=self.split_ratio)
        arrays_by_split = {
            name: self._episodes_to_arrays(records)
            for name, records in split.by_name().items()
        }
        all_observations = np.concatenate(
            [
                arrays.observations
                for arrays in arrays_by_split.values()
                if arrays.observations.size
            ],
            axis=0,
        )
        all_actions = np.concatenate(
            [arrays.actions for arrays in arrays_by_split.values() if arrays.actions.size],
            axis=0,
        )
        statistics = compute_statistics(all_observations, all_actions)
        report = quality_report(scan.episodes, arrays_by_split, broken_episodes=scan.errors)
        manifest = self._manifest(
            episodes=scan.episodes,
            dataset_name=dataset_name,
            dataset_version=dataset_version,
            sample_count=int(all_observations.shape[0]),
        )
        output = Path(output_dir)
        if output.exists():
            if not overwrite:
                raise FileExistsError(f"Dataset output already exists: {output}")
            shutil.rmtree(output)
        output.mkdir(parents=True)
        for split_name, arrays in arrays_by_split.items():
            self._save_npz(output / f"{split_name}.npz", arrays)
        self._write_json(output / "metadata.json", self._metadata(split, arrays_by_split))
        self._write_json(output / "statistics.json", statistics)
        self._write_json(output / "quality_report.json", report)
        self._write_json(output / "manifest.json", manifest)
        return DatasetBuildResult(
            output_dir=output,
            manifest=manifest,
            statistics=statistics,
            quality_report=report,
        )

    def _episodes_to_arrays(self, episodes: list[EpisodeRecord]) -> DatasetArrays:
        observations: list[np.ndarray] = []
        actions: list[np.ndarray] = []
        rewards: list[float] = []
        terminated: list[bool] = []
        truncated: list[bool] = []
        success: list[bool] = []
        episode_ids: list[str] = []
        step_indices: list[int] = []
        for episode in episodes:
            for step in episode.steps:
                observations.append(self.encoder.encode(step.observation))
                actions.append(validate_action(step.action))
                rewards.append(float(step.reward))
                terminated.append(bool(step.terminated))
                truncated.append(bool(step.truncated))
                success.append(bool(step.success))
                episode_ids.append(step.episode_id)
                step_indices.append(int(step.step_index))
        if not observations:
            observation_array = np.empty((0, self.encoder.dimension), dtype=np.float64)
            action_array = np.empty((0, 8), dtype=np.float64)
        else:
            observation_array = np.stack(observations).astype(np.float64)
            action_array = np.stack(actions).astype(np.float64)
        return DatasetArrays(
            observations=observation_array,
            actions=action_array,
            rewards=np.array(rewards, dtype=np.float64),
            terminated=np.array(terminated, dtype=np.bool_),
            truncated=np.array(truncated, dtype=np.bool_),
            success=np.array(success, dtype=np.bool_),
            episode_ids=np.array(episode_ids, dtype=str),
            step_indices=np.array(step_indices, dtype=np.int64),
        )

    def _manifest(
        self,
        *,
        episodes: list[EpisodeRecord],
        dataset_name: str,
        dataset_version: str,
        sample_count: int,
    ) -> dict[str, Any]:
        success_count = sum(1 for episode in episodes if episode.is_success)
        return build_manifest(
            dataset_name=dataset_name,
            dataset_version=dataset_version,
            source_episodes=[episode.episode_id for episode in episodes],
            split_seed=self.seed,
            split_ratio=self.split_ratio,
            feature_order=self.encoder.feature_order,
            sample_count=sample_count,
            episode_count=len(episodes),
            success_episode_count=success_count,
            failure_episode_count=len(episodes) - success_count,
            repo_root=Path.cwd(),
        )

    def _metadata(
        self,
        split: DatasetSplit,
        arrays_by_split: dict[str, DatasetArrays],
    ) -> dict[str, Any]:
        return {
            "feature_order": self.encoder.feature_order,
            "observation_dimension": self.encoder.dimension,
            "action_dimension": 8,
            "splits": {
                name: {
                    "episode_ids": [episode.episode_id for episode in episodes],
                    "sample_count": int(arrays_by_split[name].observations.shape[0]),
                }
                for name, episodes in split.by_name().items()
            },
        }

    @staticmethod
    def _save_npz(path: Path, arrays: DatasetArrays) -> None:
        np.savez_compressed(
            path,
            observations=arrays.observations,
            actions=arrays.actions,
            rewards=arrays.rewards,
            terminated=arrays.terminated,
            truncated=arrays.truncated,
            success=arrays.success,
            episode_ids=arrays.episode_ids,
            step_indices=arrays.step_indices,
        )

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_dataset_split(dataset_dir: str | Path, split_name: str) -> DatasetArrays:
    path = Path(dataset_dir) / f"{split_name}.npz"
    if not path.exists():
        raise FileNotFoundError(f"Dataset split file not found: {path}")
    data = np.load(path, allow_pickle=False)
    return DatasetArrays(
        observations=data["observations"],
        actions=data["actions"],
        rewards=data["rewards"],
        terminated=data["terminated"],
        truncated=data["truncated"],
        success=data["success"],
        episode_ids=data["episode_ids"],
        step_indices=data["step_indices"],
    )


def validate_dataset(dataset_dir: str | Path) -> dict[str, Any]:
    path = Path(dataset_dir)
    required = [
        "train.npz",
        "validation.npz",
        "test.npz",
        "metadata.json",
        "statistics.json",
        "quality_report.json",
        "manifest.json",
    ]
    missing = [name for name in required if not (path / name).exists()]
    if missing:
        raise ValueError(f"Dataset missing required files: {', '.join(missing)}")
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    expected_obs_dim = int(metadata["observation_dimension"])
    expected_action_dim = int(metadata["action_dimension"])
    seen_episode_ids: set[str] = set()
    split_summary: dict[str, Any] = {}
    total_samples = 0
    for split_name in ("train", "validation", "test"):
        arrays = load_dataset_split(path, split_name)
        if arrays.observations.ndim != 2 or arrays.observations.shape[1] != expected_obs_dim:
            raise ValueError(
                f"{split_name} observations have invalid shape {arrays.observations.shape}",
            )
        if arrays.actions.ndim != 2 or arrays.actions.shape[1] != expected_action_dim:
            raise ValueError(f"{split_name} actions have invalid shape {arrays.actions.shape}")
        sample_count = arrays.observations.shape[0]
        if arrays.actions.shape[0] != sample_count:
            raise ValueError(f"{split_name} actions sample count mismatch")
        if not np.all(np.isfinite(arrays.observations)):
            raise ValueError(f"{split_name} observations contain NaN or Inf")
        if not np.all(np.isfinite(arrays.actions)):
            raise ValueError(f"{split_name} actions contain NaN or Inf")
        if np.any((arrays.actions < -1.0) | (arrays.actions > 1.0)):
            raise ValueError(f"{split_name} actions contain values outside [-1, 1]")
        split_episode_ids = set(arrays.episode_ids.astype(str).tolist())
        overlap = seen_episode_ids.intersection(split_episode_ids)
        if overlap:
            raise ValueError(f"Episode leakage across splits: {sorted(overlap)}")
        seen_episode_ids.update(split_episode_ids)
        total_samples += sample_count
        split_summary[split_name] = {
            "sample_count": int(sample_count),
            "episode_count": len(split_episode_ids),
        }
    if int(manifest["sample_count"]) != total_samples:
        raise ValueError(
            f"Manifest sample_count {manifest['sample_count']} does not match {total_samples}",
        )
    return {
        "dataset_dir": str(path),
        "sample_count": total_samples,
        "splits": split_summary,
        "manifest": manifest,
    }
