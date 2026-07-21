from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.learning.datasets.dataset_builder import load_dataset_split


@dataclass(frozen=True, slots=True)
class BCSplit:
    observations: np.ndarray
    actions: np.ndarray
    episode_ids: np.ndarray


@dataclass(frozen=True, slots=True)
class BCDataset:
    train: BCSplit
    validation: BCSplit
    test: BCSplit
    metadata: dict[str, Any]
    manifest: dict[str, Any]
    statistics: dict[str, Any]

    @property
    def input_dim(self) -> int:
        return int(self.metadata["observation_dimension"])

    @property
    def action_dim(self) -> int:
        return int(self.metadata["action_dimension"])


def load_bc_dataset(dataset_dir: str | Path) -> BCDataset:
    path = Path(dataset_dir)
    metadata = _read_json(path / "metadata.json")
    manifest = _read_json(path / "manifest.json")
    statistics = _read_json(path / "statistics.json")
    return BCDataset(
        train=_split(path, "train"),
        validation=_split(path, "validation"),
        test=_split(path, "test"),
        metadata=metadata,
        manifest=manifest,
        statistics=statistics,
    )


def dataset_limitations(dataset: BCDataset) -> list[str]:
    warnings: list[str] = []
    episode_count = int(dataset.manifest.get("episode_count", 0))
    test_samples = int(dataset.test.observations.shape[0])
    if episode_count < 20:
        warnings.append(
            f"Dataset has only {episode_count} valid Episodes; "
            "use results only as a pipeline smoke test.",
        )
    if test_samples < 100:
        warnings.append(
            f"Test split has only {test_samples} samples; metrics are not statistically reliable.",
        )
    if dataset.test.observations.shape[0] == 0:
        warnings.append("Test split is empty; test metrics cannot be computed.")
    return warnings


def observation_normalizer(dataset: BCDataset) -> tuple[np.ndarray, np.ndarray]:
    stats = dataset.statistics["observations"]
    mean = np.array(stats["mean"], dtype=np.float64)
    safe_std = np.array(stats["safe_std"], dtype=np.float64)
    if mean.shape != (dataset.input_dim,) or safe_std.shape != (dataset.input_dim,):
        raise ValueError("Observation normalization stats do not match dataset input dimension")
    return mean, safe_std


def normalize_observations(
    observations: np.ndarray,
    mean: np.ndarray,
    safe_std: np.ndarray,
) -> np.ndarray:
    return (observations.astype(np.float64) - mean) / safe_std


def _split(path: Path, split_name: str) -> BCSplit:
    arrays = load_dataset_split(path, split_name)
    return BCSplit(
        observations=arrays.observations.astype(np.float64),
        actions=arrays.actions.astype(np.float64),
        episode_ids=arrays.episode_ids.astype(str),
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
