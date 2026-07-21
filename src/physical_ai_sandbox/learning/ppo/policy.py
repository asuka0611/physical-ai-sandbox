from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.learning.bc.policy import MLPPolicy
from physical_ai_sandbox.learning.datasets.feature_encoder import ACTION_DIMENSION


@dataclass(slots=True)
class MLPNetwork:
    weights: list[np.ndarray]
    biases: list[np.ndarray]

    @classmethod
    def initialize(
        cls,
        input_dim: int,
        output_dim: int,
        *,
        hidden_sizes: tuple[int, ...] = (64, 64),
        seed: int = 42,
    ) -> MLPNetwork:
        rng = np.random.default_rng(seed)
        dims = (input_dim, *hidden_sizes, output_dim)
        weights: list[np.ndarray] = []
        biases: list[np.ndarray] = []
        for fan_in, fan_out in zip(dims[:-1], dims[1:], strict=True):
            limit = np.sqrt(6.0 / (fan_in + fan_out))
            weights.append(rng.uniform(-limit, limit, size=(fan_in, fan_out)).astype(np.float64))
            biases.append(np.zeros(fan_out, dtype=np.float64))
        return cls(weights=weights, biases=biases)

    @classmethod
    def from_bc_policy(cls, policy: MLPPolicy) -> MLPNetwork:
        return cls(
            weights=[weight.copy().astype(np.float64) for weight in policy.weights],
            biases=[bias.copy().astype(np.float64) for bias in policy.biases],
        )

    @property
    def input_dim(self) -> int:
        return int(self.weights[0].shape[0])

    @property
    def output_dim(self) -> int:
        return int(self.weights[-1].shape[1])

    @property
    def hidden_sizes(self) -> tuple[int, ...]:
        return tuple(int(weight.shape[1]) for weight in self.weights[:-1])

    def forward(
        self,
        observations: np.ndarray,
    ) -> tuple[np.ndarray, list[np.ndarray], list[np.ndarray]]:
        activations = [observations.astype(np.float64)]
        pre_activations: list[np.ndarray] = []
        value = activations[0]
        for weight, bias in zip(self.weights[:-1], self.biases[:-1], strict=True):
            pre_activation = value @ weight + bias
            pre_activations.append(pre_activation)
            value = np.maximum(pre_activation, 0.0)
            activations.append(value)
        output = value @ self.weights[-1] + self.biases[-1]
        activations.append(output)
        return output, activations, pre_activations

    def predict(self, observations: np.ndarray) -> np.ndarray:
        output, _activations, _pre_activations = self.forward(observations)
        return output

    def gradients(
        self,
        activations: list[np.ndarray],
        pre_activations: list[np.ndarray],
        output_gradient: np.ndarray,
    ) -> tuple[list[np.ndarray], list[np.ndarray]]:
        grad = output_gradient.astype(np.float64)
        weight_grads: list[np.ndarray] = []
        bias_grads: list[np.ndarray] = []
        for layer_index in reversed(range(len(self.weights))):
            input_activation = activations[layer_index]
            weight_grads.append(input_activation.T @ grad)
            bias_grads.append(np.sum(grad, axis=0))
            if layer_index > 0:
                grad = grad @ self.weights[layer_index].T
                grad = grad * (pre_activations[layer_index - 1] > 0.0)
        weight_grads.reverse()
        bias_grads.reverse()
        return weight_grads, bias_grads

    def apply_gradients(
        self,
        weight_grads: list[np.ndarray],
        bias_grads: list[np.ndarray],
        *,
        learning_rate: float,
        scale: float = 1.0,
    ) -> None:
        for index in range(len(self.weights)):
            self.weights[index] -= learning_rate * scale * weight_grads[index]
            self.biases[index] -= learning_rate * scale * bias_grads[index]


@dataclass(slots=True)
class PPOActorCritic:
    actor: MLPNetwork
    critic: MLPNetwork
    log_std: np.ndarray
    metadata: dict[str, Any]

    @classmethod
    def initialize_random(
        cls,
        input_dim: int,
        *,
        hidden_sizes: tuple[int, ...] = (64, 64),
        seed: int = 42,
        metadata: dict[str, Any] | None = None,
    ) -> PPOActorCritic:
        return cls(
            actor=MLPNetwork.initialize(
                input_dim,
                ACTION_DIMENSION,
                hidden_sizes=hidden_sizes,
                seed=seed,
            ),
            critic=MLPNetwork.initialize(input_dim, 1, hidden_sizes=hidden_sizes, seed=seed + 1000),
            log_std=np.full(ACTION_DIMENSION, -0.5, dtype=np.float64),
            metadata=metadata or {},
        )

    @classmethod
    def initialize_from_bc(
        cls,
        bc_checkpoint: str | Path,
        *,
        seed: int = 42,
        metadata: dict[str, Any] | None = None,
    ) -> PPOActorCritic:
        bc_policy, bc_metadata = MLPPolicy.load(bc_checkpoint)
        if bc_policy.action_dim != ACTION_DIMENSION:
            raise ValueError(f"BC action_dim must be {ACTION_DIMENSION}")
        combined_metadata = {**bc_metadata, **(metadata or {})}
        return cls(
            actor=MLPNetwork.from_bc_policy(bc_policy),
            critic=MLPNetwork.initialize(
                bc_policy.input_dim,
                1,
                hidden_sizes=bc_policy.hidden_sizes,
                seed=seed + 1000,
            ),
            log_std=np.full(ACTION_DIMENSION, -2.0, dtype=np.float64),
            metadata=combined_metadata,
        )

    @property
    def input_dim(self) -> int:
        return self.actor.input_dim

    def mean(
        self,
        observations: np.ndarray,
    ) -> tuple[np.ndarray, list[np.ndarray], list[np.ndarray]]:
        raw, activations, pre_activations = self.actor.forward(observations)
        return np.tanh(raw), activations, pre_activations

    def value(self, observations: np.ndarray) -> np.ndarray:
        values = self.critic.predict(observations)[:, 0]
        return values.astype(np.float64)

    def sample_action(
        self,
        observation: np.ndarray,
        rng: np.random.Generator,
        *,
        deterministic: bool = False,
    ) -> tuple[np.ndarray, float, float]:
        observations = observation[None, :].astype(np.float64)
        mean, _activations, _pre_activations = self.mean(observations)
        std = np.exp(self.log_std)
        action = mean[0] if deterministic else mean[0] + rng.normal(0.0, std)
        clipped = np.clip(action, -1.0, 1.0).astype(np.float64)
        log_prob = self.log_prob(observations, clipped[None, :])[0]
        value = self.value(observations)[0]
        if not np.all(np.isfinite(clipped)) or not np.isfinite(log_prob) or not np.isfinite(value):
            raise FloatingPointError("PPO policy produced NaN or Inf")
        return clipped, float(log_prob), float(value)

    def log_prob(self, observations: np.ndarray, actions: np.ndarray) -> np.ndarray:
        mean, _activations, _pre_activations = self.mean(observations)
        std = np.exp(self.log_std)
        variance = std**2
        log_probs = -0.5 * (
            ((actions - mean) ** 2) / variance
            + 2.0 * self.log_std
            + np.log(2.0 * np.pi)
        )
        return np.sum(log_probs, axis=1)

    def entropy(self) -> float:
        return float(np.sum(self.log_std + 0.5 * np.log(2.0 * np.pi * np.e)))

    def save(self, path: str | Path, metadata: dict[str, Any]) -> None:
        output = Path(path)
        arrays: dict[str, np.ndarray] = {
            "metadata_json": np.array([repr(metadata)], dtype=str),
            "log_std": self.log_std.astype(np.float64),
        }
        for index, (weight, bias) in enumerate(
            zip(self.actor.weights, self.actor.biases, strict=True),
        ):
            arrays[f"actor_weight_{index}"] = weight
            arrays[f"actor_bias_{index}"] = bias
        for index, (weight, bias) in enumerate(
            zip(self.critic.weights, self.critic.biases, strict=True),
        ):
            arrays[f"critic_weight_{index}"] = weight
            arrays[f"critic_bias_{index}"] = bias
        np.savez_compressed(output, **arrays)

    @classmethod
    def load(cls, path: str | Path) -> tuple[PPOActorCritic, dict[str, Any]]:
        data = np.load(Path(path), allow_pickle=False)
        metadata = ast.literal_eval(str(data["metadata_json"][0]))
        actor_weights: list[np.ndarray] = []
        actor_biases: list[np.ndarray] = []
        critic_weights: list[np.ndarray] = []
        critic_biases: list[np.ndarray] = []
        index = 0
        while f"actor_weight_{index}" in data.files:
            actor_weights.append(data[f"actor_weight_{index}"].astype(np.float64))
            actor_biases.append(data[f"actor_bias_{index}"].astype(np.float64))
            index += 1
        index = 0
        while f"critic_weight_{index}" in data.files:
            critic_weights.append(data[f"critic_weight_{index}"].astype(np.float64))
            critic_biases.append(data[f"critic_bias_{index}"].astype(np.float64))
            index += 1
        if not actor_weights or not critic_weights:
            raise ValueError(f"No PPO weights found in {path}")
        policy = cls(
            actor=MLPNetwork(actor_weights, actor_biases),
            critic=MLPNetwork(critic_weights, critic_biases),
            log_std=data["log_std"].astype(np.float64),
            metadata=metadata,
        )
        return policy, metadata


def gradient_global_norm(
    gradient_groups: list[list[np.ndarray]],
    extra: list[np.ndarray] | None = None,
) -> float:
    total = 0.0
    for group in gradient_groups:
        for gradient in group:
            total += float(np.sum(gradient.astype(np.float64) ** 2))
    for gradient in extra or []:
        total += float(np.sum(gradient.astype(np.float64) ** 2))
    return float(np.sqrt(total))


def gradient_clip_scale(norm: float, max_norm: float) -> float:
    if max_norm <= 0.0 or norm <= max_norm:
        return 1.0
    return float(max_norm / (norm + 1e-8))
