from __future__ import annotations

import numpy as np

from physical_ai_sandbox.cli.grasp_lift_demo import collect_grasp_lift_demos
from physical_ai_sandbox.learning.bc.policy import MLPPolicy
from physical_ai_sandbox.learning.datasets.dataset_builder import DatasetBuilder
from physical_ai_sandbox.learning.datasets.feature_encoder import ObservationEncoder
from physical_ai_sandbox.learning.ppo.buffer import RolloutBuffer, compute_gae
from physical_ai_sandbox.learning.ppo.evaluation import evaluate_ppo
from physical_ai_sandbox.learning.ppo.policy import PPOActorCritic
from physical_ai_sandbox.learning.ppo.trainer import PPOTrainer, PPOTrainingConfig


def _make_dataset(tmp_path):
    episodes = tmp_path / "episodes"
    dataset = tmp_path / "dataset"
    collect_grasp_lift_demos(episodes=3, log_root=episodes, seed=7)
    DatasetBuilder(seed=7).build_from_episodes(
        episodes,
        dataset,
        dataset_name="grasp_lift_test",
        dataset_version="v1",
    )
    return dataset


def test_compute_gae_matches_manual_returns() -> None:
    rewards = np.array([1.0, 1.0, 1.0])
    dones = np.array([False, False, True])
    values = np.zeros(3)

    advantages, returns = compute_gae(
        rewards=rewards,
        dones=dones,
        values=values,
        last_value=0.0,
        gamma=1.0,
        gae_lambda=1.0,
    )

    assert np.allclose(advantages, [3.0, 2.0, 1.0])
    assert np.allclose(returns, [3.0, 2.0, 1.0])


def test_rollout_buffer_builds_batch_with_advantages() -> None:
    buffer = RolloutBuffer()
    for index in range(4):
        buffer.add(
            observation=np.zeros(29),
            action=np.zeros(8),
            reward=float(index),
            done=index == 3,
            value=0.0,
            log_prob=-1.0,
        )

    batch = buffer.to_batch(last_value=0.0, gamma=0.99, gae_lambda=0.95)

    assert batch.observations.shape == (4, 29)
    assert batch.actions.shape == (4, 8)
    assert np.all(np.isfinite(batch.advantages))
    assert np.all(np.isfinite(batch.returns))


def test_ppo_checkpoint_save_reload_and_bc_initialization(tmp_path) -> None:
    encoder = ObservationEncoder()
    bc = MLPPolicy.initialize(encoder.dimension, 8, hidden_sizes=(8,), seed=1)
    bc_checkpoint = tmp_path / "bc.npz"
    metadata = {
        "input_dim": encoder.dimension,
        "action_dim": 8,
        "feature_order": encoder.feature_order,
        "observation_mean": np.zeros(encoder.dimension).tolist(),
        "observation_safe_std": np.ones(encoder.dimension).tolist(),
    }
    bc.save(bc_checkpoint, metadata)
    policy = PPOActorCritic.initialize_from_bc(bc_checkpoint, seed=2, metadata=metadata)
    checkpoint = tmp_path / "ppo.npz"
    policy.save(checkpoint, {**metadata, "init": "bc"})

    loaded, loaded_metadata = PPOActorCritic.load(checkpoint)

    observation = np.zeros(encoder.dimension)
    action, log_prob, value = loaded.sample_action(
        observation,
        np.random.default_rng(3),
        deterministic=True,
    )
    assert loaded_metadata["init"] == "bc"
    assert action.shape == (8,)
    assert np.all(np.isfinite(action))
    assert np.isfinite(log_prob)
    assert np.isfinite(value)


def test_ppo_trainer_runs_smoke_training_reload_and_evaluation(tmp_path) -> None:
    dataset = _make_dataset(tmp_path)
    output = tmp_path / "ppo_model"
    config = PPOTrainingConfig(
        total_steps=8,
        rollout_steps=8,
        max_episode_steps=8,
        update_epochs=1,
        minibatch_size=4,
        seed=5,
        init="random",
        hidden_sizes=(8,),
    )

    result = PPOTrainer(config).train(
        output,
        dataset_dir=dataset,
        bc_model_dir=None,
    )
    reloaded, metadata = PPOActorCritic.load(result.checkpoint_path)
    report = evaluate_ppo(
        output,
        episodes=1,
        max_steps=8,
        seed=5,
        record=False,
        log_root=tmp_path / "rollouts",
    )

    assert result.checkpoint_path.exists()
    assert len(result.history) == 1
    assert metadata["init"] == "random"
    assert reloaded.input_dim == ObservationEncoder().dimension
    assert report["metrics"]["episode_count"] == 1
    assert "grasp_lift_success_rate" in report["metrics"]


def test_ppo_policy_clips_actions_and_evaluation_is_seed_reproducible(tmp_path) -> None:
    dataset = _make_dataset(tmp_path)
    output = tmp_path / "ppo_seed_model"
    config = PPOTrainingConfig(
        total_steps=8,
        rollout_steps=8,
        max_episode_steps=8,
        update_epochs=1,
        minibatch_size=4,
        seed=6,
        init="random",
        hidden_sizes=(8,),
    )
    PPOTrainer(config).train(output, dataset_dir=dataset, bc_model_dir=None)
    policy, _metadata = PPOActorCritic.load(output / "ppo_checkpoint.npz")
    policy.actor.biases[-1][:] = 100.0
    action, _log_prob, _value = policy.sample_action(
        np.zeros(ObservationEncoder().dimension),
        np.random.default_rng(1),
        deterministic=True,
    )

    first = evaluate_ppo(output, episodes=1, max_steps=8, seed=12, record=False)
    second = evaluate_ppo(output, episodes=1, max_steps=8, seed=12, record=False)

    assert np.all(action == 1.0)
    assert first["metrics"] == second["metrics"]
    assert first["failure_reasons"] == second["failure_reasons"]
