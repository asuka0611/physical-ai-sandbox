from __future__ import annotations

import json

import numpy as np

from physical_ai_sandbox.evaluation.bc_rollout import BCRolloutEvaluator, RolloutConfig
from physical_ai_sandbox.learning.bc.policy import MLPPolicy
from physical_ai_sandbox.learning.datasets.feature_encoder import ObservationEncoder


def _write_zero_checkpoint(model_dir) -> None:
    model_dir.mkdir(parents=True)
    encoder = ObservationEncoder()
    policy = MLPPolicy.initialize(encoder.dimension, 8, hidden_sizes=(8,), seed=3)
    for weight in policy.weights:
        weight[:] = 0.0
    for bias in policy.biases:
        bias[:] = 0.0
    metadata = {
        "input_dim": encoder.dimension,
        "action_dim": 8,
        "feature_order": encoder.feature_order,
        "observation_mean": np.zeros(encoder.dimension).tolist(),
        "observation_safe_std": np.ones(encoder.dimension).tolist(),
        "warnings": ["Dataset has only 5 valid Episodes; smoke test only."],
    }
    policy.save(model_dir / "policy_checkpoint.npz", metadata)


def test_bc_rollout_evaluator_runs_headless_and_reports_metrics(tmp_path) -> None:
    model_dir = tmp_path / "model"
    report_path = tmp_path / "rollout_report.json"
    _write_zero_checkpoint(model_dir)

    report = BCRolloutEvaluator(
        model_dir,
        log_root=tmp_path / "episodes",
        rollout_config=RolloutConfig(episodes=2, max_steps=4, seed=11, record=False, replay=False),
    ).evaluate(report_path=report_path)

    assert report_path.exists()
    assert report["metrics"]["episode_count"] == 2
    assert set(report["metrics"]) >= {
        "success_rate",
        "average_total_reward",
        "grasp_rate",
        "lift_rate",
        "grasp_lift_success_rate",
        "goal_reached_rate",
    }
    assert sum(report["failure_reasons"].values()) == 2
    assert report["warnings"]
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["metrics"] == report["metrics"]


def test_bc_rollout_records_and_replays_episode(tmp_path) -> None:
    model_dir = tmp_path / "model"
    _write_zero_checkpoint(model_dir)

    report = BCRolloutEvaluator(
        model_dir,
        log_root=tmp_path / "episodes",
        rollout_config=RolloutConfig(episodes=1, max_steps=3, seed=5, record=True, replay=True),
    ).evaluate()

    episode = report["episodes"][0]
    assert episode["episode_dir"] is not None
    assert episode["replay"] is not None
    assert episode["replay"]["steps"] == episode["steps"]
    assert report["metrics"]["replay_count"] == 1


def test_bc_rollout_seed_reproducibility_for_metrics(tmp_path) -> None:
    model_dir = tmp_path / "model"
    _write_zero_checkpoint(model_dir)
    config = RolloutConfig(episodes=2, max_steps=4, seed=123, record=False, replay=False)

    first = BCRolloutEvaluator(model_dir, rollout_config=config).evaluate()
    second = BCRolloutEvaluator(model_dir, rollout_config=config).evaluate()

    assert first["metrics"] == second["metrics"]
    assert first["failure_reasons"] == second["failure_reasons"]
    assert [item["final_observation"] for item in first["episodes"]] == [
        item["final_observation"] for item in second["episodes"]
    ]
