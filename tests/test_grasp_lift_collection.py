from __future__ import annotations

import json

from physical_ai_sandbox.cli.grasp_lift_demo import collect_grasp_lift_demos
from physical_ai_sandbox.learning.datasets.episode_loader import EpisodeLoader


def test_collect_grasp_lift_demos_records_successful_fixed_condition_episodes(tmp_path) -> None:
    report = collect_grasp_lift_demos(episodes=2, log_root=tmp_path, seed=9)

    assert report["episode_count"] == 2
    assert report["fixed_initial_condition"] is True
    assert report["grasp_rate"] == 1.0
    assert report["lift_rate"] == 1.0
    assert report["task_success_rate"] == 1.0
    saved = json.loads((tmp_path / "collection_report.json").read_text(encoding="utf-8"))
    assert saved["collector_version"].startswith("phase3.6")
    scan = EpisodeLoader().scan(tmp_path)
    assert len(scan.episodes) == 2
    assert not scan.errors
    assert all(episode.is_success for episode in scan.episodes)
