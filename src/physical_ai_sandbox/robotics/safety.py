from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from physical_ai_sandbox.learning.datasets.feature_encoder import ACTION_DIMENSION


@dataclass(frozen=True, slots=True)
class SafetyResult:
    action: np.ndarray
    safe: bool
    reason: str | None = None


class SafetyLayer:
    def __init__(self, *, max_delta: float = 0.35) -> None:
        self.max_delta = float(max_delta)
        self._last_action = np.zeros(ACTION_DIMENSION, dtype=np.float64)
        self._emergency_stop = False
        self._emergency_reason = "emergency_stop"

    def reset(self) -> None:
        self._last_action = np.zeros(ACTION_DIMENSION, dtype=np.float64)
        self._emergency_stop = False
        self._emergency_reason = "emergency_stop"

    def emergency_stop(self, reason: str = "emergency_stop") -> None:
        self._emergency_stop = True
        self._emergency_reason = reason
        self._last_action = np.zeros(ACTION_DIMENSION, dtype=np.float64)

    def filter_action(self, action: np.ndarray | list[float]) -> SafetyResult:
        if self._emergency_stop:
            return SafetyResult(
                np.zeros(ACTION_DIMENSION, dtype=np.float64), False, self._emergency_reason
            )
        array = np.asarray(action, dtype=np.float64)
        if array.shape != (ACTION_DIMENSION,):
            return SafetyResult(
                np.zeros(ACTION_DIMENSION, dtype=np.float64), False, "invalid_action_shape"
            )
        if not np.all(np.isfinite(array)):
            return SafetyResult(
                np.zeros(ACTION_DIMENSION, dtype=np.float64), False, "non_finite_action"
            )
        clipped = np.clip(array, -1.0, 1.0)
        delta = np.clip(clipped - self._last_action, -self.max_delta, self.max_delta)
        limited = self._last_action + delta
        self._last_action = limited
        reason = "clipped_or_rate_limited" if not np.allclose(limited, array) else None
        return SafetyResult(limited.astype(np.float64), True, reason)
