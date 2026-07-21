from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.learning.bc.dataset import (
    BCDataset,
    dataset_limitations,
    load_bc_dataset,
    normalize_observations,
    observation_normalizer,
)
from physical_ai_sandbox.learning.bc.evaluation import evaluate_policy
from physical_ai_sandbox.learning.bc.policy import MLPPolicy

TRAINER_VERSION = "phase3.behavior_cloning.numpy_mlp.v1"


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    epochs: int = 80
    batch_size: int = 64
    learning_rate: float = 0.01
    seed: int = 42
    hidden_sizes: tuple[int, ...] = (64, 64)


@dataclass(frozen=True, slots=True)
class TrainingResult:
    output_dir: Path
    history: list[dict[str, float | int | None]]
    evaluation: dict[str, Any]
    checkpoint_path: Path


class BehaviorCloningTrainer:
    def __init__(self, config: TrainingConfig | None = None) -> None:
        self.config = config or TrainingConfig()

    def train_from_dataset(
        self,
        dataset_dir: str | Path,
        output_dir: str | Path,
        *,
        overwrite: bool = True,
    ) -> TrainingResult:
        dataset = load_bc_dataset(dataset_dir)
        mean, safe_std = observation_normalizer(dataset)
        normalized = self._normalized_dataset(dataset, mean, safe_std)
        policy = MLPPolicy.initialize(
            normalized.input_dim,
            normalized.action_dim,
            hidden_sizes=self.config.hidden_sizes,
            seed=self.config.seed,
        )
        rng = np.random.default_rng(self.config.seed)
        history = self._train(policy, normalized, rng)
        evaluation = evaluate_policy(policy, normalized)
        output = Path(output_dir)
        if output.exists() and overwrite:
            import shutil

            shutil.rmtree(output)
        output.mkdir(parents=True, exist_ok=True)
        checkpoint_path = output / "policy_checkpoint.npz"
        metadata = self._checkpoint_metadata(dataset, mean, safe_std)
        policy.save(checkpoint_path, metadata)
        self._write_json(output / "training_history.json", {"history": history})
        self._write_json(output / "evaluation_report.json", evaluation)
        self._write_json(output / "metadata.json", metadata)
        return TrainingResult(
            output_dir=output,
            history=history,
            evaluation=evaluation,
            checkpoint_path=checkpoint_path,
        )

    def _train(
        self,
        policy: MLPPolicy,
        dataset: BCDataset,
        rng: np.random.Generator,
    ) -> list[dict[str, float | int | None]]:
        train_x = dataset.train.observations
        train_y = dataset.train.actions
        if train_x.shape[0] == 0:
            raise ValueError("Training split is empty")
        history: list[dict[str, float | int | None]] = []
        for epoch in range(1, self.config.epochs + 1):
            order = rng.permutation(train_x.shape[0])
            for start in range(0, train_x.shape[0], self.config.batch_size):
                batch_indices = order[start : start + self.config.batch_size]
                self._train_batch(policy, train_x[batch_indices], train_y[batch_indices])
            train_loss = self._mse(policy, dataset.train)
            validation_loss = self._mse(policy, dataset.validation)
            history.append(
                {
                    "epoch": epoch,
                    "train_mse": train_loss,
                    "validation_mse": validation_loss,
                },
            )
        return history

    def _train_batch(
        self,
        policy: MLPPolicy,
        observations: np.ndarray,
        targets: np.ndarray,
    ) -> None:
        predictions, activations, pre_activations = policy.forward_with_cache(observations)
        grad = 2.0 * (predictions - targets) / targets.shape[0]
        weight_grads: list[np.ndarray] = []
        bias_grads: list[np.ndarray] = []
        for layer_index in reversed(range(len(policy.weights))):
            input_activation = activations[layer_index]
            weight_grads.append(input_activation.T @ grad)
            bias_grads.append(np.sum(grad, axis=0))
            if layer_index > 0:
                grad = grad @ policy.weights[layer_index].T
                grad = grad * (pre_activations[layer_index - 1] > 0.0)
        weight_grads.reverse()
        bias_grads.reverse()
        for index in range(len(policy.weights)):
            policy.weights[index] -= self.config.learning_rate * weight_grads[index]
            policy.biases[index] -= self.config.learning_rate * bias_grads[index]

    @staticmethod
    def _mse(policy: MLPPolicy, split) -> float | None:
        if split.observations.shape[0] == 0:
            return None
        predictions = policy.predict(split.observations)
        return float(np.mean((predictions - split.actions) ** 2))

    @staticmethod
    def _normalized_dataset(
        dataset: BCDataset,
        mean: np.ndarray,
        safe_std: np.ndarray,
    ) -> BCDataset:
        from physical_ai_sandbox.learning.bc.dataset import BCSplit

        return BCDataset(
            train=BCSplit(
                observations=normalize_observations(dataset.train.observations, mean, safe_std),
                actions=dataset.train.actions,
                episode_ids=dataset.train.episode_ids,
            ),
            validation=BCSplit(
                observations=normalize_observations(
                    dataset.validation.observations,
                    mean,
                    safe_std,
                ),
                actions=dataset.validation.actions,
                episode_ids=dataset.validation.episode_ids,
            ),
            test=BCSplit(
                observations=normalize_observations(dataset.test.observations, mean, safe_std),
                actions=dataset.test.actions,
                episode_ids=dataset.test.episode_ids,
            ),
            metadata=dataset.metadata,
            manifest=dataset.manifest,
            statistics=dataset.statistics,
        )

    def _checkpoint_metadata(
        self,
        dataset: BCDataset,
        mean: np.ndarray,
        safe_std: np.ndarray,
    ) -> dict[str, Any]:
        return {
            "created_at": datetime.now(UTC).isoformat(),
            "trainer_version": TRAINER_VERSION,
            "dataset_name": dataset.manifest.get("dataset_name"),
            "dataset_version": dataset.manifest.get("dataset_version"),
            "dataset_sample_count": dataset.manifest.get("sample_count"),
            "dataset_episode_count": dataset.manifest.get("episode_count"),
            "input_dim": dataset.input_dim,
            "action_dim": dataset.action_dim,
            "hidden_sizes": list(self.config.hidden_sizes),
            "epochs": self.config.epochs,
            "batch_size": self.config.batch_size,
            "learning_rate": self.config.learning_rate,
            "seed": self.config.seed,
            "feature_order": dataset.metadata.get("feature_order", []),
            "observation_mean": mean.tolist(),
            "observation_safe_std": safe_std.tolist(),
            "warnings": dataset_limitations(dataset),
        }

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
