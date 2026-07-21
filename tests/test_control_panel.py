from __future__ import annotations

from physical_ai_sandbox.ui.control_panel import ControlCommandQueue, ControlPanelStateStore
from physical_ai_sandbox.ui.control_types import (
    ControlPanelSnapshot,
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


def test_snapshot_message_roundtrip() -> None:
    snapshot = ControlPanelSnapshot(step=5, max_steps=1000, last_event="ready", language="ja")

    restored = ControlPanelSnapshot.from_message(snapshot.to_message())

    assert restored.step == 5
    assert restored.max_steps == 1000
    assert restored.last_event == "ready"


def test_runtime_uses_separate_mjpython_viewer_process() -> None:
    runtime = __import__(
        "physical_ai_sandbox.ui.control_panel",
        fromlist=["ControlPanelRuntime"],
    ).ControlPanelRuntime(show_viewer=True)

    command = runtime._build_simulation_command("127.0.0.1", 12345, "00")

    assert command[:3] == [command[0], "run", "mjpython"]
    assert "physical_ai_sandbox.ui.simulation_process" in command


def test_runtime_no_viewer_uses_current_python() -> None:
    runtime = __import__(
        "physical_ai_sandbox.ui.control_panel",
        fromlist=["ControlPanelRuntime"],
    ).ControlPanelRuntime(show_viewer=False)

    command = runtime._build_simulation_command("127.0.0.1", 12345, "00")

    assert command[1] == "-m"
    assert "physical_ai_sandbox.ui.simulation_process" in command
    assert "--no-viewer" in command
