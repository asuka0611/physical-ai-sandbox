from __future__ import annotations

from physical_ai_sandbox.controllers.manual import ManualController


def test_manual_controller_selects_all_joints_and_moves() -> None:
    controller = ManualController()
    for key in "1234567":
        controller.handle_key(ord(key))
        assert controller.selected_joint == int(key) - 1
        controller.handle_key(262)
        action = controller.action()
        assert action[int(key) - 1] == 1.0


def test_manual_controller_previous_next_and_gripper() -> None:
    controller = ManualController()
    controller.handle_key(ord("7"))
    controller.handle_key(ord("]"))
    assert controller.selected_joint == 0
    controller.handle_key(ord("["))
    assert controller.selected_joint == 6
    controller.handle_key(32)
    assert controller.action()[7] == 1.0
    controller.handle_key(32)
    assert controller.action()[7] == -1.0
