from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.learning.datasets.feature_encoder import (
    ACTION_DIMENSION,
    ObservationEncoder,
)
from physical_ai_sandbox.learning.ppo.policy import PPOActorCritic
from physical_ai_sandbox.policies.base import PolicyAction, safe_stop
from physical_ai_sandbox.types import Observation


class PPOPolicy:
    name = "ppo"

    def __init__(self, model_path: str | Path, *, seed: int = 42) -> None:
        self.model_path = Path(model_path)
        self.checkpoint_path = self._resolve_checkpoint(self.model_path)
        self.policy, self._metadata = PPOActorCritic.load(self.checkpoint_path)
        self.encoder = ObservationEncoder()
        self.observation_mean = self._metadata_vector("observation_mean")
        self.observation_safe_std = self._metadata_vector("observation_safe_std")
        self._validate_contract()
        self._seed = int(seed)
        self._rng = np.random.default_rng(self._seed)

    @staticmethod
    def _resolve_checkpoint(model_path: str | Path) -> Path:
        path = Path(model_path)
        if path.is_dir():
            path = path / "ppo_checkpoint.npz"
        if not path.exists():
            raise FileNotFoundError(f"PPO checkpoint not found: {path}")
        return path

    def _metadata_vector(self, key: str) -> np.ndarray:
        value = self._metadata.get(key)
        if value is None:
            raise ValueError(f"PPO checkpoint metadata missing {key}")
        vector = np.asarray(value, dtype=np.float64)
        if vector.shape != (self.encoder.dimension,):
            raise ValueError(
                f"PPO checkpoint metadata {key} has shape {vector.shape}, "
                f"expected {(self.encoder.dimension,)}",
            )
        if not np.all(np.isfinite(vector)):
            raise ValueError(f"PPO checkpoint metadata {key} contains NaN or Inf")
        return vector

    def _validate_contract(self) -> None:
        if self.policy.input_dim != self.encoder.dimension:
            raise ValueError(
                f"PPO input_dim {self.policy.input_dim} does not match "
                f"{self.encoder.dimension}",
            )
        if self.policy.actor.output_dim != ACTION_DIMENSION:
            raise ValueError(
                f"PPO action_dim {self.policy.actor.output_dim} does not match {ACTION_DIMENSION}",
            )
        if np.any(self.observation_safe_std <= 0.0):
            raise ValueError("PPO observation_safe_std must be strictly positive")

    def reset(self, *, seed: int | None = None) -> None:
        if seed is not None:
            self._seed = int(seed)
        self._rng = np.random.default_rng(self._seed)

    def act(self, observation: Observation, *, deterministic: bool = True) -> PolicyAction:
        try:
            normalized = (
                self.encoder.encode(observation) - self.observation_mean
            ) / self.observation_safe_std
        except ValueError as exc:
            return safe_stop(f"invalid_observation: {exc}", policy_name=self.name)
        if not np.all(np.isfinite(normalized)):
            return safe_stop("non_finite_normalized_observation", policy_name=self.name)
        try:
            action, _log_prob, _value = self.policy.sample_action(
                normalized,
                self._rng,
                deterministic=deterministic,
            )
        except FloatingPointError as exc:
            return safe_stop(str(exc), policy_name=self.name)
        return PolicyAction(action=action).clipped()

    def close(self) -> None:
        return None

    def metadata(self) -> dict[str, Any]:
        return {
            "policy": self.name,
            "model_path": str(self.model_path),
            "checkpoint_path": str(self.checkpoint_path),
            "checkpoint_metadata": self._metadata,
        }
