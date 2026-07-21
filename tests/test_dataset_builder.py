from __future__ import annotations

import json

from physical_ai_sandbox.learning.datasets.dataset_builder import (
    DatasetBuilder,
    load_dataset_split,
    validate_dataset,
)
from tests.dataset_test_utils import make_episode


def test_dataset_builder_saves_and_validates_dataset(tmp_path) -> None:
    episodes_root = tmp_path / "episodes"
    output = tmp_path / "dataset"
    for index in range(5):
        make_episode(episodes_root, f"episode_{index}", success=index == 0)
    broken = make_episode(episodes_root, "episode_broken")
    (broken / "summary.json").unlink()
    result = DatasetBuilder(seed=42).build_from_episodes(episodes_root, output)
    assert result.manifest["episode_count"] == 5
    assert "episode_broken" in result.quality_report["broken_episodes"]
    validation = validate_dataset(output)
    assert validation["sample_count"] == 20
    train = load_dataset_split(output, "train")
    assert train.observations.shape[1] == 29
    assert train.actions.shape[1] == 8
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["observation_dimension"] == 29


def test_dataset_validation_detects_action_out_of_range(tmp_path) -> None:
    episodes_root = tmp_path / "episodes"
    output = tmp_path / "dataset"
    make_episode(episodes_root, "episode_0")
    DatasetBuilder(seed=42).build_from_episodes(episodes_root, output)
    split = load_dataset_split(output, "train")
    split.actions[0, 0] = 2.0
    import numpy as np

    np.savez_compressed(
        output / "train.npz",
        observations=split.observations,
        actions=split.actions,
        rewards=split.rewards,
        terminated=split.terminated,
        truncated=split.truncated,
        success=split.success,
        episode_ids=split.episode_ids,
        step_indices=split.step_indices,
    )
    import pytest

    with pytest.raises(ValueError, match="outside"):
        validate_dataset(output)
