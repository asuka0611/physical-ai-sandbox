from __future__ import annotations

import numpy as np

from physical_ai_sandbox.learning.bc.dataset import dataset_limitations, load_bc_dataset
from physical_ai_sandbox.learning.bc.evaluation import evaluate_policy
from physical_ai_sandbox.learning.bc.policy import MLPPolicy
from physical_ai_sandbox.learning.bc.trainer import BehaviorCloningTrainer, TrainingConfig
from physical_ai_sandbox.learning.datasets.dataset_builder import DatasetBuilder
from tests.dataset_test_utils import make_episode


def test_mlp_policy_predict_shape_and_checkpoint(tmp_path) -> None:
    policy = MLPPolicy.initialize(29, 8, hidden_sizes=(8,), seed=1)
    observations = np.zeros((3, 29), dtype=float)
    predictions = policy.predict(observations)
    assert predictions.shape == (3, 8)
    checkpoint = tmp_path / "policy.npz"
    policy.save(checkpoint, {"input_dim": 29, "action_dim": 8})
    loaded, metadata = MLPPolicy.load(checkpoint)
    assert metadata["input_dim"] == 29
    assert np.allclose(predictions, loaded.predict(observations))


def test_behavior_cloning_trainer_writes_artifacts_and_warns_about_small_data(tmp_path) -> None:
    episodes_root = tmp_path / "episodes"
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "model"
    for index in range(5):
        make_episode(episodes_root, f"episode_{index}", success=index % 2 == 0, steps=8)
    DatasetBuilder(seed=7).build_from_episodes(episodes_root, dataset_dir)
    config = TrainingConfig(epochs=8, batch_size=8, learning_rate=0.01, seed=7, hidden_sizes=(16,))
    result = BehaviorCloningTrainer(config).train_from_dataset(dataset_dir, output_dir)
    assert (output_dir / "policy_checkpoint.npz").exists()
    assert (output_dir / "training_history.json").exists()
    assert (output_dir / "evaluation_report.json").exists()
    assert len(result.history) == 8
    assert result.history[-1]["train_mse"] is not None
    assert result.evaluation["warnings"]


def test_evaluate_policy_reports_supervised_metrics(tmp_path) -> None:
    episodes_root = tmp_path / "episodes"
    dataset_dir = tmp_path / "dataset"
    for index in range(3):
        make_episode(episodes_root, f"episode_{index}", success=True, steps=6)
    DatasetBuilder(seed=3).build_from_episodes(episodes_root, dataset_dir)
    dataset = load_bc_dataset(dataset_dir)
    policy = MLPPolicy.initialize(dataset.input_dim, dataset.action_dim, hidden_sizes=(8,), seed=3)
    report = evaluate_policy(policy, dataset)
    assert report["train"]["sample_count"] > 0
    assert report["interpretation"].startswith("Metrics report supervised")
    assert dataset_limitations(dataset)
