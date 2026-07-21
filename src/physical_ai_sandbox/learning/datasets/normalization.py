from __future__ import annotations

from typing import Any

import numpy as np


def compute_array_stats(array: np.ndarray) -> dict[str, Any]:
    if array.ndim != 2:
        raise ValueError(f"Expected 2D array for stats, got shape {array.shape}")
    if array.shape[0] == 0:
        raise ValueError("Cannot compute stats for empty array")
    if not np.all(np.isfinite(array)):
        raise ValueError("Cannot compute stats for array containing NaN or Inf")
    std = array.std(axis=0)
    safe_std = np.where(std < 1e-8, 1.0, std)
    return {
        "mean": array.mean(axis=0).tolist(),
        "std": std.tolist(),
        "safe_std": safe_std.tolist(),
        "min": array.min(axis=0).tolist(),
        "max": array.max(axis=0).tolist(),
        "count": int(array.shape[0]),
        "zero_variance_indices": np.where(std < 1e-8)[0].astype(int).tolist(),
    }


def compute_statistics(observations: np.ndarray, actions: np.ndarray) -> dict[str, Any]:
    return {
        "observations": compute_array_stats(observations),
        "actions": compute_array_stats(actions),
    }
