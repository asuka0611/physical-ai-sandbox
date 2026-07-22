from __future__ import annotations

from typing import Any

import numpy as np

from physical_ai_sandbox.learning.datasets.feature_encoder import ACTION_DIMENSION
from physical_ai_sandbox.policies.base import PolicyAction
from physical_ai_sandbox.types import Observation


class RandomPolicy:
    name = "random"

    def __init__(self, *, action_scale: float = 1.0, seed: int = 42) -> None:
        self.action_scale = float(action_scale)
        self._seed = seed
        self._rng = np.random.default_rng(seed)

    def reset(self, *, seed: int | None = None) -> None:
        if seed is not None:
            self._seed = int(seed)
        self._rng = np.random.default_rng(self._seed)

    def act(self, observation: Observation, *, deterministic: bool = True) -> PolicyAction:
        del observation, deterministic
        action = self._rng.uniform(-self.action_scale, self.action_scale, size=ACTION_DIMENSION)
        return PolicyAction(action=np.clip(action, -1.0, 1.0))

    def close(self) -> None:
        return None

    def metadata(self) -> dict[str, Any]:
        return {"policy": self.name, "action_scale": self.action_scale, "seed": self._seed}
