from __future__ import annotations

from dataclasses import dataclass

from physical_ai_sandbox.ui.input_manager import InputContext, InputManager


class EntryWidget:
    def winfo_class(self) -> str:
        return "Entry"


class FrameWidget:
    def winfo_class(self) -> str:
        return "Frame"


@dataclass
class Event:
    keysym: str
    widget: object
    char: str = ""
    state: int = 0


def test_entry_focus_blocks_robot_shortcuts() -> None:
    manager = InputManager()
    manager.focus_in(EntryWidget())

    assert manager.context == InputContext.TEXT_ENTRY
    assert manager.handle_key_press(Event("w", EntryWidget())) is None


def test_viewport_focus_dispatches_shortcuts_and_suppresses_repeat() -> None:
    manager = InputManager()
    widget = FrameWidget()
    manager.focus_in(widget)

    assert manager.handle_key_press(Event("w", widget), now=1.0) == "x_positive"
    assert manager.handle_key_press(Event("w", widget), now=1.01) is None
    assert manager.handle_key_press(Event("w", widget), now=1.2) == "x_positive"


def test_escape_clears_text_focus() -> None:
    manager = InputManager()
    widget = EntryWidget()
    manager.focus_in(widget)

    assert manager.handle_key_press(Event("Escape", widget)) == "clear_focus"


def test_command_modifier_does_not_drive_robot() -> None:
    manager = InputManager()
    widget = FrameWidget()
    manager.focus_in(widget)

    assert manager.handle_key_press(Event("w", widget, state=0x10)) is None


def test_focus_out_clears_pressed_keys() -> None:
    manager = InputManager()
    widget = FrameWidget()
    manager.focus_in(widget)
    manager.handle_key_press(Event("w", widget), now=1.0)

    manager.focus_out()

    assert manager.pressed_keys == set()
    assert manager.context == InputContext.VIEWPORT
