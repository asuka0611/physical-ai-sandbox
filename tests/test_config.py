from __future__ import annotations

import pytest

from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH
from physical_ai_sandbox.scene.config import load_and_validate_config, validate_config


def test_default_config_validates() -> None:
    config = load_and_validate_config(DEFAULT_CONFIG_PATH)
    assert config["scene"]["name"] == "panda_pick_place_phase1"


def test_invalid_obstacle_shape_rejected() -> None:
    config = load_and_validate_config(DEFAULT_CONFIG_PATH)
    config["objects"][0]["type"] = "sphere"
    with pytest.raises(ValueError, match="Invalid scene config"):
        validate_config(config)
