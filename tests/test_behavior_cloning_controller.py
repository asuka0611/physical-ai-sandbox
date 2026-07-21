from __future__ import annotations

import numpy as np
import pytest

from physical_ai_sandbox.controllers.behavior_cloning import BehaviorCloningController
from physical_ai_sandbox.learning.bc.policy import MLPPolicy
from physical_ai_sandbox.learning.datasets.feature_encoder import ObservationEncoder
from tests.dataset_test_utils import observation


def _write_checkpoint(path, *, output_bias: float = 0.0, metadata_override=None) -> None:
    encoder = ObservationEncoder()
    policy = MLPPolicy.initialize(encoder.dimension, 8, hidden_sizes=(8,), seed=1)
    for weight in policy.weights:
        weight[:] = 0.0
    for bias in policy.biases:
        bias[:] = 0.0
    policy.biases[-1][:] = output_bias
    metadata = {
        "input_dim": encoder.dimension,
        "action_dim": 8,
        "feature_order": encoder.feature_order,
        "observation_mean": np.zeros(encoder.dimension).tolist(),
        "observation_safe_std": np.ones(encoder.dimension).tolist(),
        "warnings": ["small dataset"],
    }
    if metadata_override:
        metadata.update(metadata_override)
    policy.save(path, metadata)


def test_behavior_cloning_controller_loads_checkpoint_and_clips_action(tmp_path) -> None:
    checkpoint = tmp_path / "policy_checkpoint.npz"
    _write_checkpoint(checkpoint, output_bias=5.0)
    controller = BehaviorCloningController(checkpoint)

    output = controller.act(observation())

    assert output.is_safe
    assert output.unsafe_reason is None
    assert output.action.shape == (8,)
    assert np.all(output.action == 1.0)


def test_behavior_cloning_controller_uses_metadata_normalization_contract(tmp_path) -> None:
    checkpoint = tmp_path / "policy_checkpoint.npz"
    _write_checkpoint(checkpoint)
    controller = BehaviorCloningController(tmp_path)

    assert controller.observation_mean.shape == (ObservationEncoder().dimension,)
    assert np.all(controller.observation_safe_std == 1.0)


def test_behavior_cloning_controller_returns_safe_stop_for_nan_observation(tmp_path) -> None:
    checkpoint = tmp_path / "policy_checkpoint.npz"
    _write_checkpoint(checkpoint)
    controller = BehaviorCloningController(checkpoint)
    bad_observation = observation()
    bad_observation["cube_position"] = [float("nan"), 0.0, 0.41]

    output = controller.act(bad_observation)

    assert not output.is_safe
    assert output.unsafe_reason is not None
    assert output.unsafe_reason.startswith("invalid_observation")
    assert np.all(output.action == 0.0)


def test_behavior_cloning_controller_returns_safe_stop_for_nan_policy_output(tmp_path) -> None:
    checkpoint = tmp_path / "policy_checkpoint.npz"
    _write_checkpoint(checkpoint, output_bias=float("nan"))
    controller = BehaviorCloningController(checkpoint)

    output = controller.act(observation())

    assert not output.is_safe
    assert output.unsafe_reason == "non_finite_policy_action"
    assert np.all(output.action == 0.0)


def test_behavior_cloning_controller_rejects_bad_checkpoint_dimensions(tmp_path) -> None:
    checkpoint = tmp_path / "policy_checkpoint.npz"
    _write_checkpoint(checkpoint, metadata_override={"input_dim": 28})

    with pytest.raises(ValueError, match="input_dim"):
        BehaviorCloningController(checkpoint)
