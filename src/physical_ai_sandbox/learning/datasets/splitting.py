from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from physical_ai_sandbox.learning.datasets.episode_dataset import EpisodeRecord


@dataclass(frozen=True, slots=True)
class DatasetSplit:
    train: list[EpisodeRecord]
    validation: list[EpisodeRecord]
    test: list[EpisodeRecord]

    def by_name(self) -> dict[str, list[EpisodeRecord]]:
        return {"train": self.train, "validation": self.validation, "test": self.test}


def split_episodes(
    episodes: list[EpisodeRecord],
    *,
    seed: int = 42,
    ratios: tuple[float, float, float] = (0.8, 0.1, 0.1),
) -> DatasetSplit:
    if not episodes:
        raise ValueError("Cannot split an empty episode list")
    if not np.isclose(sum(ratios), 1.0):
        raise ValueError(f"Split ratios must sum to 1.0, got {ratios}")
    episode_ids = [episode.episode_id for episode in episodes]
    if len(set(episode_ids)) != len(episode_ids):
        raise ValueError("Duplicate episode_id detected before split")
    rng = np.random.default_rng(seed)
    shuffled = list(episodes)
    order = rng.permutation(len(shuffled))
    shuffled = [shuffled[index] for index in order]
    count = len(shuffled)
    if count == 1:
        return DatasetSplit(train=shuffled, validation=[], test=[])
    if count == 2:
        return DatasetSplit(train=shuffled[:1], validation=shuffled[1:], test=[])
    train_count = max(1, int(round(count * ratios[0])))
    validation_count = max(1, int(round(count * ratios[1])))
    if train_count + validation_count >= count:
        validation_count = 1
        train_count = count - 2
    test_count = count - train_count - validation_count
    if test_count < 1:
        test_count = 1
        train_count = count - validation_count - test_count
    split = DatasetSplit(
        train=shuffled[:train_count],
        validation=shuffled[train_count : train_count + validation_count],
        test=shuffled[train_count + validation_count :],
    )
    seen: set[str] = set()
    for split_name, split_episodes_list in split.by_name().items():
        for episode in split_episodes_list:
            if episode.episode_id in seen:
                raise ValueError(f"Episode {episode.episode_id} appears in multiple splits")
            seen.add(episode.episode_id)
            if not split_name:
                raise ValueError("Split name cannot be empty")
    return split
