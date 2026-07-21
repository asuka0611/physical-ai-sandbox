from __future__ import annotations

import pytest

from physical_ai_sandbox.learning.datasets.episode_loader import EpisodeLoader, EpisodeLoadError
from tests.dataset_test_utils import make_episode


def test_load_valid_episode(tmp_path) -> None:
    episode_dir = make_episode(tmp_path, "episode_a", success=True)
    episode = EpisodeLoader().load_episode(episode_dir)
    assert episode.episode_id == "episode_a"
    assert episode.is_success is True
    assert episode.length == 4


def test_scan_reports_missing_summary(tmp_path) -> None:
    episode_dir = make_episode(tmp_path, "episode_b")
    (episode_dir / "summary.json").unlink()
    result = EpisodeLoader().scan(tmp_path)
    assert result.episodes == []
    assert "episode_b" in result.errors


def test_load_many_rejects_broken_by_default(tmp_path) -> None:
    make_episode(tmp_path, "episode_ok")
    broken = make_episode(tmp_path, "episode_broken")
    (broken / "steps.jsonl").unlink()
    with pytest.raises(EpisodeLoadError, match="Broken episodes detected"):
        EpisodeLoader().load_many(tmp_path)
