from __future__ import annotations

import json

import numpy as np

from physical_ai_sandbox.cli.replay_episode import replay_episode
from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv


def test_episode_recording_writes_required_files(tmp_path) -> None:
    env = PandaPickPlaceEnv(log_root=tmp_path)
    episode_dir = env.start_recording({"test": True})
    for _ in range(3):
        env.step(np.zeros(8))
    env.stop_recording({"test": True})
    assert (episode_dir / "metadata.json").exists()
    assert (episode_dir / "steps.jsonl").exists()
    assert (episode_dir / "summary.json").exists()
    lines = (episode_dir / "steps.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    payload = json.loads(lines[0])
    required_keys = [
        "observation",
        "action",
        "reward",
        "episode_id",
        "step",
        "time",
        "success",
        "grasp_state",
    ]
    for key in required_keys:
        assert key in payload
    env.close()


def test_replay_episode_runs_actions(tmp_path) -> None:
    env = PandaPickPlaceEnv(log_root=tmp_path)
    episode_dir = env.start_recording({"test": "replay"})
    for _ in range(4):
        env.step([0.1, 0, 0, 0, 0, 0, 0, -1])
    env.stop_recording({"test": "replay"})
    env.close()
    result = replay_episode(episode_dir, max_steps=4)
    assert result["steps"] == 4
