from __future__ import annotations

from physical_ai_sandbox.learning.datasets.episode_loader import EpisodeLoader
from physical_ai_sandbox.learning.datasets.splitting import split_episodes
from tests.dataset_test_utils import make_episode


def test_episode_level_split_has_no_leakage_and_is_reproducible(tmp_path) -> None:
    for index in range(10):
        make_episode(tmp_path, f"episode_{index}", success=index % 2 == 0)
    episodes = EpisodeLoader().load_many(tmp_path)
    split_a = split_episodes(episodes, seed=123)
    split_b = split_episodes(episodes, seed=123)
    ids_a = {
        name: [episode.episode_id for episode in eps]
        for name, eps in split_a.by_name().items()
    }
    ids_b = {
        name: [episode.episode_id for episode in eps]
        for name, eps in split_b.by_name().items()
    }
    assert ids_a == ids_b
    seen: set[str] = set()
    for split_ids in ids_a.values():
        assert seen.isdisjoint(split_ids)
        seen.update(split_ids)
    assert len(seen) == 10
