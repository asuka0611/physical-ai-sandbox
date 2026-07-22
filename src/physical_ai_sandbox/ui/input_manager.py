from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class InputContext(Enum):
    GLOBAL = "global"
    VIEWPORT = "viewport"
    TEXT_ENTRY = "text_entry"
    JOINT_CONTROL = "joint_control"
    TIMELINE = "timeline"
    DISABLED = "disabled"


class KeyEvent(Protocol):
    keysym: str
    char: str
    state: int
    widget: object


@dataclass(slots=True)
class InputManager:
    """Central keyboard focus and shortcut router for the Tk workspace."""

    key_bindings: dict[str, str] = field(default_factory=dict)
    repeat_window_seconds: float = 0.08
    context: InputContext = InputContext.VIEWPORT
    last_command: str | None = None
    focused_widget: str = ""
    pressed_keys: set[str] = field(default_factory=set)
    _last_key_times: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key_bindings:
            self.key_bindings.update(default_key_bindings())

    def focus_in(self, widget: object) -> InputContext:
        self.focused_widget = widget_class_name(widget)
        self.context = context_for_widget(widget)
        return self.context

    def focus_out(self) -> None:
        self.focused_widget = ""
        self.context = InputContext.VIEWPORT
        self.clear_pressed_keys()

    def clear_pressed_keys(self) -> None:
        self.pressed_keys.clear()
        self._last_key_times.clear()

    def handle_key_press(self, event: KeyEvent, *, now: float | None = None) -> str | None:
        if self.context == InputContext.DISABLED:
            return None
        key = normalize_key(event)
        self.pressed_keys.add(key)
        if self._is_text_entry(event):
            if key == "escape":
                self.last_command = "clear_focus"
                return "clear_focus"
            return None
        if has_command_modifier(event):
            return None
        timestamp = time.monotonic() if now is None else now
        if self._is_repeat(key, timestamp):
            return None
        command = self.key_bindings.get(key)
        self.last_command = command
        return command

    def handle_key_release(self, event: KeyEvent) -> None:
        self.pressed_keys.discard(normalize_key(event))

    def _is_text_entry(self, event: KeyEvent) -> bool:
        return context_for_widget(event.widget) == InputContext.TEXT_ENTRY

    def _is_repeat(self, key: str, timestamp: float) -> bool:
        previous = self._last_key_times.get(key)
        self._last_key_times[key] = timestamp
        return previous is not None and timestamp - previous < self.repeat_window_seconds

    def debug_snapshot(self) -> dict[str, object]:
        return {
            "input_context": self.context.value,
            "focused_widget": self.focused_widget,
            "pressed_keys": sorted(self.pressed_keys),
            "last_command": self.last_command,
        }


def default_key_bindings() -> dict[str, str]:
    return {
        "w": "x_positive",
        "s": "x_negative",
        "a": "y_negative",
        "d": "y_positive",
        "r": "z_positive",
        "f": "z_negative",
        "q": "rotate_negative",
        "e": "rotate_positive",
        "o": "open_gripper",
        "c": "close_gripper",
        "space": "toggle_pause",
        "return": "reset",
        "escape": "clear_focus",
    }


def normalize_key(event: KeyEvent) -> str:
    key = str(getattr(event, "keysym", "") or getattr(event, "char", "")).lower()
    if key in {" ", "space"}:
        return "space"
    if key in {"enter", "return"}:
        return "return"
    if key in {"esc", "escape"}:
        return "escape"
    return key


def has_command_modifier(event: KeyEvent) -> bool:
    # Tk on macOS uses Mod2/Command in the 0x10 bit for many builds. Keeping this
    # conservative prevents Command+key menu shortcuts from driving the robot.
    return bool(int(getattr(event, "state", 0)) & 0x10)


def widget_class_name(widget: object) -> str:
    try:
        return str(widget.winfo_class())  # type: ignore[attr-defined]
    except Exception:
        return widget.__class__.__name__


def context_for_widget(widget: object) -> InputContext:
    name = widget_class_name(widget).lower()
    if name in {"entry", "text", "spinbox", "combobox", "tentry", "tcombobox"}:
        return InputContext.TEXT_ENTRY
    if "scale" in name or "button" in name:
        return InputContext.JOINT_CONTROL
    return InputContext.VIEWPORT
