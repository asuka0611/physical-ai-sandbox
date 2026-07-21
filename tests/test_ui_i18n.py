from __future__ import annotations

from physical_ai_sandbox.ui.i18n import TRANSLATIONS, translate

REQUIRED_KEYS = [
    "start",
    "pause",
    "resume",
    "reset",
    "stop",
    "manual_control",
    "behavior_cloning",
    "ppo",
    "episode",
    "step",
    "reward",
    "grasped",
    "lifted",
    "success",
    "failure",
    "recording",
    "start_recording",
    "stop_recording",
    "open_gripper",
    "close_gripper",
    "robot_status",
    "experiment_status",
    "controller",
    "environment",
    "language",
    "camera",
    "help",
    "quit",
]


def test_required_translation_keys_have_japanese_and_english() -> None:
    for key in REQUIRED_KEYS:
        assert key in TRANSLATIONS
        assert translate(key, "en")
        assert translate(key, "ja")


def test_translation_falls_back_without_exception() -> None:
    assert translate("start", "unsupported") == "Start"
    assert translate("missing_key", "ja") == "missing_key"
