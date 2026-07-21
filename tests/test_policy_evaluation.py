from __future__ import annotations

import csv
import json

import numpy as np
import pytest

from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv
from physical_ai_sandbox.evaluation.policy_compare import compare_policies
from physical_ai_sandbox.evaluation.policy_runner import PolicyEvaluationConfig, evaluate_policy
from physical_ai_sandbox.learning.bc.policy import MLPPolicy
from physical_ai_sandbox.learning.datasets.feature_encoder import (
    ACTION_DIMENSION,
    ObservationEncoder,
)
from physical_ai_sandbox.learning.ppo.policy import PPOActorCritic
from physical_ai_sandbox.policies.bc import BehaviorCloningPolicy
from physical_ai_sandbox.policies.factory import create_policy
from physical_ai_sandbox.policies.ppo import PPOPolicy
from physical_ai_sandbox.policies.random import RandomPolicy


def _metadata() -> dict[str, object]:
    encoder = ObservationEncoder()
    return {
        "input_dim": encoder.dimension,
        "action_dim": ACTION_DIMENSION,
        "feature_order": encoder.feature_order,
        "observation_mean": np.zeros(encoder.dimension).tolist(),
        "observation_safe_std": np.ones(encoder.dimension).tolist(),
    }


def _make_bc_model(tmp_path):
    encoder = ObservationEncoder()
    model_dir = tmp_path / "bc_model"
    model_dir.mkdir()
    policy = MLPPolicy.initialize(encoder.dimension, ACTION_DIMENSION, hidden_sizes=(8,), seed=3)
    policy.save(model_dir / "policy_checkpoint.npz", _metadata())
    return model_dir


def _make_ppo_model(tmp_path):
    encoder = ObservationEncoder()
    model_dir = tmp_path / "ppo_model"
    model_dir.mkdir()
    policy = PPOActorCritic.initialize_random(encoder.dimension, hidden_sizes=(8,), seed=4)
    policy.save(model_dir / "ppo_checkpoint.npz", {**_metadata(), "init": "random"})
    return model_dir


def _sample_observation():
    env = PandaPickPlaceEnv()
    try:
        return env.reset()
    finally:
        env.close()


def test_random_policy_seed_reproducibility() -> None:
    observation = _sample_observation()
    first = RandomPolicy(seed=10)
    second = RandomPolicy(seed=10)

    first.reset(seed=99)
    second.reset(seed=99)
    action_a = first.act(observation).action
    action_b = second.act(observation).action

    assert action_a.shape == (ACTION_DIMENSION,)
    assert np.allclose(action_a, action_b)
    assert np.all(action_a <= 1.0)
    assert np.all(action_a >= -1.0)


def test_bc_and_ppo_policy_load_and_act(tmp_path) -> None:
    observation = _sample_observation()
    bc = BehaviorCloningPolicy(_make_bc_model(tmp_path))
    ppo = PPOPolicy(_make_ppo_model(tmp_path), seed=11)

    bc_action = bc.act(observation)
    ppo.reset(seed=11)
    ppo_action = ppo.act(observation, deterministic=True)

    assert bc_action.is_safe
    assert ppo_action.is_safe
    assert bc_action.action.shape == (ACTION_DIMENSION,)
    assert ppo_action.action.shape == (ACTION_DIMENSION,)
    assert bc.metadata()["policy"] == "bc"
    assert ppo.metadata()["policy"] == "ppo"


def test_invalid_model_paths_fail() -> None:
    with pytest.raises(FileNotFoundError):
        create_policy("bc", model_path="missing_bc_model")
    with pytest.raises(FileNotFoundError):
        create_policy("ppo", model_path="missing_ppo_model")


def test_policy_evaluation_writes_json_csv_and_is_seed_reproducible(tmp_path) -> None:
    output = tmp_path / "random_report.json"
    csv_output = tmp_path / "random_report.csv"
    config = PolicyEvaluationConfig(
        episodes=2,
        max_steps=3,
        seed=7,
        log_root=tmp_path / "rollouts",
        save_trajectory=True,
    )

    first = evaluate_policy(
        RandomPolicy(seed=7),
        config=config,
        output=output,
        csv_output=csv_output,
    )
    second = evaluate_policy(RandomPolicy(seed=7), config=config)

    assert output.exists()
    assert csv_output.exists()
    assert json.loads(output.read_text())["metrics"] == first["metrics"]
    assert first["metrics"] == second["metrics"]
    assert first["failure_reasons"] == second["failure_reasons"]
    with csv_output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[0]["policy_name"] == "random"
    assert "action_trajectory" in first["episodes"][0]


def test_policy_comparison_writes_json_csv_markdown(tmp_path) -> None:
    report = compare_policies(
        ["random"],
        episodes=1,
        seed=12,
        max_steps=2,
        output_dir=tmp_path / "comparison",
    )

    assert report["summary"][0]["policy"] == "random"
    assert (tmp_path / "comparison" / "comparison_report.json").exists()
    assert (tmp_path / "comparison" / "comparison_summary.csv").exists()
    assert (tmp_path / "comparison" / "comparison_summary.md").exists()


def test_viewer_mode_is_not_enabled_until_ui_replay_phase(tmp_path) -> None:
    with pytest.raises(NotImplementedError):
        evaluate_policy(
            RandomPolicy(seed=1),
            config=PolicyEvaluationConfig(
                episodes=1,
                max_steps=1,
                headless=False,
                log_root=tmp_path,
            ),
        )
