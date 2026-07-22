from __future__ import annotations

from typing import Final, Literal

Language = Literal["en", "ja"]

DEFAULT_LANGUAGE: Final[Language] = "en"
SUPPORTED_LANGUAGES: Final[tuple[Language, ...]] = ("en", "ja")

TRANSLATIONS: Final[dict[str, dict[Language, str]]] = {
    "app_name": {"en": "Physical AI Sandbox", "ja": "Physical AI Sandbox"},
    "start": {"en": "Start", "ja": "開始"},
    "pause": {"en": "Pause", "ja": "一時停止"},
    "resume": {"en": "Resume", "ja": "再開"},
    "reset": {"en": "Reset", "ja": "リセット"},
    "stop": {"en": "Stop", "ja": "停止"},
    "manual_control": {"en": "Manual Control", "ja": "手動操作"},
    "behavior_cloning": {"en": "Behavior Cloning", "ja": "Behavior Cloning"},
    "ppo": {"en": "PPO", "ja": "PPO"},
    "episode": {"en": "Episode", "ja": "エピソード"},
    "step": {"en": "Step", "ja": "ステップ"},
    "reward": {"en": "Reward", "ja": "報酬"},
    "grasped": {"en": "Grasped", "ja": "把持"},
    "lifted": {"en": "Lifted", "ja": "持ち上げ"},
    "success": {"en": "Success", "ja": "成功"},
    "failure": {"en": "Failure", "ja": "失敗"},
    "recording": {"en": "Recording", "ja": "記録中"},
    "start_recording": {"en": "Start Recording", "ja": "記録開始"},
    "stop_recording": {"en": "Stop Recording", "ja": "記録停止"},
    "open_gripper": {"en": "Open Gripper", "ja": "グリッパーを開く"},
    "close_gripper": {"en": "Close Gripper", "ja": "グリッパーを閉じる"},
    "robot_status": {"en": "Robot Status", "ja": "ロボット状態"},
    "experiment_status": {"en": "Experiment Status", "ja": "実験状態"},
    "controller": {"en": "Controller", "ja": "コントローラ"},
    "environment": {"en": "Environment", "ja": "環境"},
    "language": {"en": "Language", "ja": "言語"},
    "camera": {"en": "Camera", "ja": "カメラ"},
    "reset_camera": {"en": "Reset Camera", "ja": "カメラリセット"},
    "help": {"en": "Help", "ja": "ヘルプ"},
    "quit": {"en": "Quit", "ja": "終了"},
    "running": {"en": "Running", "ja": "実行中"},
    "paused": {"en": "Paused", "ja": "一時停止中"},
    "ready": {"en": "Ready", "ja": "待機中"},
    "yes": {"en": "Yes", "ja": "はい"},
    "no": {"en": "No", "ja": "いいえ"},
    "xyz_control": {"en": "XYZ Control", "ja": "XYZ操作"},
    "rotation": {"en": "Rotation", "ja": "回転"},
    "step_size": {"en": "Step Size", "ja": "操作量"},
    "joints": {"en": "Joints", "ja": "関節"},
    "last_event": {"en": "Last Event", "ja": "最後の操作"},
    "keyboard_help": {"en": "Keyboard Help", "ja": "キーボード操作"},
}


def normalize_language(language: str | None) -> Language:
    if language in SUPPORTED_LANGUAGES:
        return language
    return DEFAULT_LANGUAGE


def translate(key: str, language: str | None = DEFAULT_LANGUAGE) -> str:
    normalized = normalize_language(language)
    values = TRANSLATIONS.get(key)
    if values is None:
        return key
    return values.get(normalized) or values.get(DEFAULT_LANGUAGE) or key
