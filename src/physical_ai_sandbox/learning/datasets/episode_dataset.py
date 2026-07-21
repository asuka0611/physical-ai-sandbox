from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class EpisodeStep:
    episode_id: str
    step_index: int
    timestamp: float
    observation: dict[str, Any]
    action: list[float]
    reward: float
    terminated: bool
    truncated: bool
    success: bool


@dataclass(frozen=True, slots=True)
class EpisodeRecord:
    episode_id: str
    path: Path
    metadata: dict[str, Any]
    summary: dict[str, Any]
    steps: list[EpisodeStep]

    @property
    def is_success(self) -> bool:
        summary = self.summary.get("summary", {})
        if isinstance(summary, dict) and "success" in summary:
            return bool(summary["success"])
        return bool(self.steps and self.steps[-1].success)

    @property
    def length(self) -> int:
        return len(self.steps)


@dataclass(frozen=True, slots=True)
class DatasetArrays:
    observations: np.ndarray
    actions: np.ndarray
    rewards: np.ndarray
    terminated: np.ndarray
    truncated: np.ndarray
    success: np.ndarray
    episode_ids: np.ndarray
    step_indices: np.ndarray
