from __future__ import annotations

import numpy as np


class ManualController:
    def __init__(self) -> None:
        self.selected_joint = 0
        self.gripper_closed = False
        self.paused = False
        self.record_toggle_requested = False
        self.reset_requested = False
        self.quit_requested = False
        self.camera_reset_requested = False
        self.last_event = "ready"
        self._pending_direction = 0.0

    def next_joint(self) -> None:
        self.selected_joint = (self.selected_joint + 1) % 7
        self.last_event = f"selected joint {self.selected_joint + 1}"

    def previous_joint(self) -> None:
        self.selected_joint = (self.selected_joint - 1) % 7
        self.last_event = f"selected joint {self.selected_joint + 1}"

    def select_joint(self, index: int) -> None:
        if not 0 <= index < 7:
            raise ValueError(f"Joint index must be 0..6, got {index}")
        self.selected_joint = index
        self.last_event = f"selected joint {self.selected_joint + 1}"

    def move_negative(self) -> None:
        self._pending_direction = -1.0
        self.last_event = f"joint {self.selected_joint + 1} negative"

    def move_positive(self) -> None:
        self._pending_direction = 1.0
        self.last_event = f"joint {self.selected_joint + 1} positive"

    def toggle_gripper(self) -> None:
        self.gripper_closed = not self.gripper_closed
        state = "closed" if self.gripper_closed else "open"
        self.last_event = f"gripper {state}"

    def action(self) -> list[float]:
        action = np.zeros(8, dtype=float)
        action[self.selected_joint] = self._pending_direction
        action[7] = 1.0 if self.gripper_closed else -1.0
        self._pending_direction = 0.0
        return action.tolist()

    def handle_key(self, key: int) -> None:
        # MuJoCo viewer forwards GLFW key codes. The passive viewer key callback
        # does not expose modifiers on all MuJoCo versions, so [ and ] are
        # reliable previous/next-joint fallbacks for Shift+Tab / Tab.
        glfw_tab = 258
        glfw_escape = 256
        glfw_left = 263
        glfw_right = 262
        glfw_space = 32
        if ord("1") <= key <= ord("7"):
            self.select_joint(key - ord("1"))
        elif key in {glfw_tab, ord("]")} :
            self.next_joint()
        elif key == ord("["):
            self.previous_joint()
        elif key == glfw_left:
            self.move_negative()
        elif key == glfw_right:
            self.move_positive()
        elif key == glfw_space:
            self.toggle_gripper()
        elif key == ord("R"):
            self.reset_requested = True
            self.last_event = "reset requested"
        elif key == ord("P"):
            self.paused = not self.paused
            self.last_event = "paused" if self.paused else "resumed"
        elif key == ord("L"):
            self.record_toggle_requested = True
            self.last_event = "record toggle requested"
        elif key == ord("C"):
            self.camera_reset_requested = True
            self.last_event = "camera reset requested"
        elif key == glfw_escape:
            self.quit_requested = True
            self.last_event = "quit requested"
