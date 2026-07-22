from __future__ import annotations

from physical_ai_sandbox.ui.control_panel import (
    ControlCommandQueue,
    ControlPanelSnapshot,
    ControlPanelStateStore,
    GuiActionMapper,
    PanelCommand,
)


def test_command_queue_drains_in_order() -> None:
    queue = ControlCommandQueue()
    queue.put("start")
    queue.put("x_positive")

    assert queue.drain() == [PanelCommand("start"), PanelCommand("x_positive")]
    assert queue.drain() == []


def test_state_store_updates_snapshot_atomically() -> None:
    store = ControlPanelStateStore(ControlPanelSnapshot(language="ja"))

    snapshot = store.update(running=True, paused=False, step=12, reward=1.25)

    assert snapshot.running is True
    assert store.snapshot().paused is False
    assert store.snapshot().step == 12
    assert store.snapshot().reward == 1.25


def test_gui_action_mapper_preserves_fixed_eight_dimensional_action() -> None:
    mapper = GuiActionMapper(step_size=0.5)

    mapper.apply(PanelCommand("x_positive"))
    mapper.apply(PanelCommand("joint_negative", 6))
    mapper.apply(PanelCommand("close_gripper"))
    action = mapper.consume_action()

    assert len(action) == 8
    assert action[1] < 0.0
    assert action[6] < 0.0
    assert action[7] == 1.0
    assert mapper.consume_action()[:7] == [0.0] * 7


def test_gui_action_mapper_opens_gripper_and_clips_step_size() -> None:
    mapper = GuiActionMapper(step_size=1.0)

    mapper.apply(PanelCommand("set_step_size", 10.0))
    mapper.apply(PanelCommand("z_positive"))
    mapper.apply(PanelCommand("open_gripper"))
    action = mapper.consume_action()

    assert max(abs(value) for value in action[:7]) <= 1.0
    assert action[7] == -1.0
