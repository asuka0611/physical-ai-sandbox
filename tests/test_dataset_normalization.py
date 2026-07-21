from __future__ import annotations

import numpy as np

from physical_ai_sandbox.learning.datasets.normalization import compute_statistics


def test_normalization_stats_include_safe_std_for_zero_variance() -> None:
    observations = np.ones((3, 2), dtype=float)
    actions = np.array([[0.0, 1.0], [0.0, -1.0], [0.0, 0.0]], dtype=float)
    stats = compute_statistics(observations, actions)
    assert stats["observations"]["zero_variance_indices"] == [0, 1]
    assert stats["observations"]["safe_std"] == [1.0, 1.0]
    assert stats["actions"]["count"] == 3
