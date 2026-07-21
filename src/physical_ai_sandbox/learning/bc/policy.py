from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(slots=True)
class MLPPolicy:
    weights: list[np.ndarray]
    biases: list[np.ndarray]

    @classmethod
    def initialize(
        cls,
        input_dim: int,
        action_dim: int,
        *,
        hidden_sizes: tuple[int, ...] = (64, 64),
        seed: int = 42,
    ) -> MLPPolicy:
        rng = np.random.default_rng(seed)
        dims = (input_dim, *hidden_sizes, action_dim)
        weights: list[np.ndarray] = []
        biases: list[np.ndarray] = []
        for fan_in, fan_out in zip(dims[:-1], dims[1:], strict=True):
            limit = np.sqrt(6.0 / (fan_in + fan_out))
            weights.append(rng.uniform(-limit, limit, size=(fan_in, fan_out)).astype(np.float64))
            biases.append(np.zeros(fan_out, dtype=np.float64))
        return cls(weights=weights, biases=biases)

    @property
    def input_dim(self) -> int:
        return int(self.weights[0].shape[0])

    @property
    def action_dim(self) -> int:
        return int(self.weights[-1].shape[1])

    @property
    def hidden_sizes(self) -> tuple[int, ...]:
        return tuple(int(weight.shape[1]) for weight in self.weights[:-1])

    def predict(self, observations: np.ndarray) -> np.ndarray:
        activations = observations.astype(np.float64)
        for weight, bias in zip(self.weights[:-1], self.biases[:-1], strict=True):
            activations = np.maximum(activations @ weight + bias, 0.0)
        actions = activations @ self.weights[-1] + self.biases[-1]
        return np.clip(actions, -1.0, 1.0)

    def forward_with_cache(
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

    def save(self, path: str | Path, metadata: dict[str, Any]) -> None:
        output = Path(path)
        arrays: dict[str, np.ndarray] = {"metadata_json": np.array([repr(metadata)], dtype=str)}
        for index, (weight, bias) in enumerate(zip(self.weights, self.biases, strict=True)):
            arrays[f"weight_{index}"] = weight
            arrays[f"bias_{index}"] = bias
        np.savez_compressed(output, **arrays)

    @classmethod
    def load(cls, path: str | Path) -> tuple[MLPPolicy, dict[str, Any]]:
        import ast

        data = np.load(Path(path), allow_pickle=False)
        metadata = ast.literal_eval(str(data["metadata_json"][0]))
        weights: list[np.ndarray] = []
        biases: list[np.ndarray] = []
        index = 0
        while f"weight_{index}" in data.files:
            weights.append(data[f"weight_{index}"].astype(np.float64))
            biases.append(data[f"bias_{index}"].astype(np.float64))
            index += 1
        if not weights:
            raise ValueError(f"No policy weights found in {path}")
        return cls(weights=weights, biases=biases), metadata
