from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from physical_ai_sandbox.ui.i18n import Language


@dataclass(frozen=True, slots=True)
class PanelCommand:
    name: str
    value: object | None = None

    def to_message(self) -> dict[str, object]:
        return {"type": "command", "name": self.name, "value": self.value}

    @classmethod
    def from_message(cls, message: dict[str, object]) -> PanelCommand:
        return cls(name=str(message["name"]), value=message.get("value"))


@dataclass(frozen=True, slots=True)
class ControlPanelSnapshot:
    app_name: str = "Physical AI Sandbox"
    running: bool = False
    paused: bool = True
    episode: int = 1
    step: int = 0
    max_steps: int = 0
    reward: float = 0.0
    session_step: int = 0
    elapsed_seconds: float = 0.0
    grasped: bool = False
    lifted: bool = False
    success: bool = False
    recording: bool = False
    controller: str = "Manual Control"
    mode: str = "Manual Test"
    environment: str = "panda_pick_place"
    language: Language = "ja"
    last_event: str = "ready"
    error_message: str | None = None
    selected_joint: int | None = None
    viewer_connected: bool = False
    input_context: str = "viewport"

    def to_message(self) -> dict[str, object]:
        return {"type": "snapshot", **asdict(self)}

    @classmethod
    def from_message(cls, message: dict[str, object]) -> ControlPanelSnapshot:
        values = {key: value for key, value in message.items() if key != "type"}
        return cls(**values)  # type: ignore[arg-type]


class GuiActionMapper:
    _ACTION_PRESETS: dict[str, tuple[float, float, float, float, float, float, float]] = {
        "x_positive": (0.0, -0.45, 0.0, 0.55, 0.0, 0.20, 0.0),
        "x_negative": (0.0, 0.45, 0.0, -0.55, 0.0, -0.20, 0.0),
        "y_positive": (0.70, 0.0, 0.20, 0.0, 0.0, 0.0, 0.0),
        "y_negative": (-0.70, 0.0, -0.20, 0.0, 0.0, 0.0, 0.0),
        "z_positive": (0.0, -0.55, 0.0, -0.35, 0.0, 0.45, 0.0),
        "z_negative": (0.0, 0.55, 0.0, 0.35, 0.0, -0.45, 0.0),
        "rotate_positive": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.75),
        "rotate_negative": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.75),
    }

    def __init__(self, step_size: float = 0.8) -> None:
        self.step_size = step_size
        self.gripper_closed = False
        self._pending = np.zeros(7, dtype=float)

    def apply(self, command: PanelCommand) -> str | None:
        if command.name == "set_step_size" and command.value is not None:
            self.step_size = float(np.clip(float(command.value), 0.1, 1.0))
            return f"step size {self.step_size:.2f}"
        if command.name == "open_gripper":
            self.gripper_closed = False
            return "gripper open"
        if command.name == "close_gripper":
            self.gripper_closed = True
            return "gripper closed"
        if command.name in self._ACTION_PRESETS:
            preset = np.array(self._ACTION_PRESETS[command.name], dtype=float)
            self._pending += preset * self.step_size
            return command.name
        if command.name in {"joint_positive", "joint_negative"} and command.value is not None:
            index = int(command.value)
            if not 0 <= index < 7:
                raise ValueError(f"Joint index must be 0..6, got {index}")
            direction = 1.0 if command.name == "joint_positive" else -1.0
            self._pending[index] += direction * self.step_size
            return f"joint {index + 1} {'positive' if direction > 0 else 'negative'}"
        if command.name == "emergency_stop":
            self.clear()
            self.gripper_closed = False
            return "emergency stop"
        return None

    def clear(self) -> None:
        self._pending[:] = 0.0

    def consume_action(self) -> list[float]:
        action = np.zeros(8, dtype=float)
        action[:7] = np.clip(self._pending, -1.0, 1.0)
        action[7] = 1.0 if self.gripper_closed else -1.0
        self._pending[:] = 0.0
        return action.tolist()
