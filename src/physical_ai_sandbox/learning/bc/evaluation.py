from __future__ import annotations

from typing import Any

import numpy as np

from physical_ai_sandbox.learning.bc.dataset import BCDataset, BCSplit, dataset_limitations
from physical_ai_sandbox.learning.bc.policy import MLPPolicy


def evaluate_split(policy: MLPPolicy, split: BCSplit) -> dict[str, Any]:
    if split.observations.shape[0] == 0:
        return {
            "sample_count": 0,
            "mse": None,
            "mae": None,
            "max_abs_error": None,
            "per_action_mse": [],
        }
    predictions = policy.predict(split.observations)
    error = predictions - split.actions
    return {
        "sample_count": int(split.observations.shape[0]),
        "mse": float(np.mean(error**2)),
        "mae": float(np.mean(np.abs(error))),
        "max_abs_error": float(np.max(np.abs(error))),
        "per_action_mse": np.mean(error**2, axis=0).tolist(),
    }


def evaluate_policy(policy: MLPPolicy, dataset: BCDataset) -> dict[str, Any]:
    return {
        "train": evaluate_split(policy, dataset.train),
        "validation": evaluate_split(policy, dataset.validation),
        "test": evaluate_split(policy, dataset.test),
        "warnings": dataset_limitations(dataset),
        "interpretation": (
            "Metrics report supervised action prediction error only. "
            "With the current small dataset, do not interpret these numbers "
            "as robot-task performance."
        ),
    }
