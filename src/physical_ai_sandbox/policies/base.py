from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from physical_ai_sandbox.learning.datasets.feature_encoder import ACTION_DIMENSION
from physical_ai_sandbox.types import Observation


@dataclass(frozen=True, slots=True)
class PolicyAction:
    action: np.ndarray
    is_safe: bool = True
    unsafe_reason: str | None = None

    def __post_init__(self) -> None:
        array = np.asarray(self.action, dtype=np.float64)
        object.__setattr__(self, "action", array)
        if array.shape != (ACTION_DIMENSION,):
            raise ValueError(
                f"Policy action must have shape {(ACTION_DIMENSION,)}, got {array.shape}",
            )
        if not np.all(np.isfinite(array)):
            raise ValueError("Policy action contains NaN or Inf")

    def clipped(self) -> PolicyAction:
        return PolicyAction(
            action=np.clip(self.action, -1.0, 1.0),
            is_safe=self.is_safe,
            unsafe_reason=self.unsafe_reason,
        )


class Policy(Protocol):
    name: str

    def reset(self, *, seed: int | None = None) -> None: ...

    def act(self, observation: Observation, *, deterministic: bool = True) -> PolicyAction: ...

    def close(self) -> None: ...

    def metadata(self) -> dict[str, Any]: ...


def safe_stop(reason: str, *, policy_name: str | None = None) -> PolicyAction:
    detail = f"{policy_name}: {reason}" if policy_name else reason
    return PolicyAction(
        action=np.zeros(ACTION_DIMENSION, dtype=np.float64),
        is_safe=False,
        unsafe_reason=detail,
    )
