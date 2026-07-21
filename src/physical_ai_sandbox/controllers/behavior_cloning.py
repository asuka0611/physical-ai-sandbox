from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.learning.bc.policy import MLPPolicy
from physical_ai_sandbox.learning.datasets.feature_encoder import (
    ACTION_DIMENSION,
    ObservationEncoder,
)
from physical_ai_sandbox.types import Observation


@dataclass(frozen=True, slots=True)
class ControllerOutput:
    action: np.ndarray
    is_safe: bool
    unsafe_reason: str | None = None

    def action_list(self) -> list[float]:
        return self.action.astype(float).tolist()


class BehaviorCloningController:
    """Closed-loop controller for Phase 3 Behavior Cloning checkpoints."""

    def __init__(self, model_path: str | Path) -> None:
        checkpoint_path = self._resolve_checkpoint(model_path)
        self.checkpoint_path = checkpoint_path
        self.policy, self.metadata = MLPPolicy.load(checkpoint_path)
        self.encoder = ObservationEncoder()
        self.observation_mean = self._metadata_vector("observation_mean")
        self.observation_safe_std = self._metadata_vector("observation_safe_std")
        self._validate_checkpoint_contract()

    @staticmethod
    def _resolve_checkpoint(model_path: str | Path) -> Path:
        path = Path(model_path)
        if path.is_dir():
            path = path / "policy_checkpoint.npz"
        if not path.exists():
            raise FileNotFoundError(f"Behavior Cloning checkpoint not found: {path}")
        return path

    def _metadata_vector(self, key: str) -> np.ndarray:
        value = self.metadata.get(key)
        if value is None:
            raise ValueError(f"Checkpoint metadata missing {key}")
        vector = np.asarray(value, dtype=np.float64)
        if vector.shape != (self.encoder.dimension,):
            raise ValueError(
                f"Checkpoint metadata {key} has shape {vector.shape}, "
                f"expected {(self.encoder.dimension,)}",
            )
        if not np.all(np.isfinite(vector)):
            raise ValueError(f"Checkpoint metadata {key} contains NaN or Inf")
        return vector

    def _validate_checkpoint_contract(self) -> None:
        if self.policy.input_dim != self.encoder.dimension:
            raise ValueError(
                f"Policy input_dim {self.policy.input_dim} does not match encoded "
                f"observation dimension {self.encoder.dimension}",
            )
        if self.policy.action_dim != ACTION_DIMENSION:
            raise ValueError(
                f"Policy action_dim {self.policy.action_dim} does not match {ACTION_DIMENSION}",
            )
        metadata_input_dim = self.metadata.get("input_dim")
        if metadata_input_dim is not None and int(metadata_input_dim) != self.encoder.dimension:
            raise ValueError(
                f"Checkpoint metadata input_dim {metadata_input_dim} does not match "
                f"{self.encoder.dimension}",
            )
        metadata_action_dim = self.metadata.get("action_dim")
        if metadata_action_dim is not None and int(metadata_action_dim) != ACTION_DIMENSION:
            raise ValueError(
                f"Checkpoint metadata action_dim {metadata_action_dim} does not match "
                f"{ACTION_DIMENSION}",
            )
        feature_order = self.metadata.get("feature_order")
        if feature_order and list(feature_order) != self.encoder.feature_order:
            raise ValueError("Checkpoint feature_order does not match ObservationEncoder order")
        if np.any(self.observation_safe_std <= 0.0):
            raise ValueError("Checkpoint observation_safe_std must be strictly positive")

    @property
    def safe_stop_action(self) -> np.ndarray:
        return np.zeros(ACTION_DIMENSION, dtype=np.float64)

    def act(self, observation: Observation | dict[str, Any]) -> ControllerOutput:
        try:
            encoded = self.encoder.encode(observation)
        except ValueError as exc:
            return self._unsafe_stop(f"invalid_observation: {exc}")
        normalized = (encoded - self.observation_mean) / self.observation_safe_std
        if not np.all(np.isfinite(normalized)):
            return self._unsafe_stop("non_finite_normalized_observation")
        raw_action = self.policy.predict(normalized[None, :])[0]
        if raw_action.shape != (ACTION_DIMENSION,):
            return self._unsafe_stop(f"invalid_policy_action_shape: {raw_action.shape}")
        if not np.all(np.isfinite(raw_action)):
            return self._unsafe_stop("non_finite_policy_action")
        clipped = np.clip(raw_action.astype(np.float64), -1.0, 1.0)
        if not np.all(np.isfinite(clipped)):
            return self._unsafe_stop("non_finite_clipped_action")
        return ControllerOutput(action=clipped, is_safe=True)

    def action(self, observation: Observation | dict[str, Any]) -> list[float]:
        return self.act(observation).action_list()

    def _unsafe_stop(self, reason: str) -> ControllerOutput:
        return ControllerOutput(action=self.safe_stop_action, is_safe=False, unsafe_reason=reason)
