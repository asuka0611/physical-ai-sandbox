from __future__ import annotations

import math

import pytest

from physical_ai_sandbox.learning.datasets.feature_encoder import (
    ObservationEncoder,
    validate_action,
)
from tests.dataset_test_utils import observation


def test_observation_encoder_dimension_and_bool_conversion() -> None:
    encoder = ObservationEncoder()
    vector = encoder.encode(observation())
    assert vector.shape == (29,)
    assert encoder.feature_order[-3:] == ["is_grasped", "is_success", "elapsed_time"]
    assert vector[-3] == 1.0


def test_observation_encoder_rejects_missing_field() -> None:
    obs = observation()
    obs.pop("cube_position")
    with pytest.raises(ValueError, match="missing required field"):
        ObservationEncoder().encode(obs)


def test_observation_encoder_rejects_nan() -> None:
    obs = observation()
    obs["joint_positions"][0] = math.nan
    with pytest.raises(ValueError, match="NaN or Inf"):
        ObservationEncoder().encode(obs)


def test_action_validation_dimension_and_inf() -> None:
    assert validate_action([0.0] * 8).shape == (8,)
    with pytest.raises(ValueError, match="expected"):
        validate_action([0.0] * 7)
    bad = [0.0] * 8
    bad[0] = math.inf
    with pytest.raises(ValueError, match="NaN or Inf"):
        validate_action(bad)
