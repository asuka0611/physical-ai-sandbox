from __future__ import annotations

import base64
from types import SimpleNamespace

import numpy as np

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
    snapshot = ControlPanelSnapshot(
        step=5,
        max_steps=1000,
        last_event="ready",
        language="ja",
        selected_joint=2,
        viewer_connected=True,
    )

    restored = ControlPanelSnapshot.from_message(snapshot.to_message())

    assert restored.step == 5
    assert restored.max_steps == 1000
    assert restored.last_event == "ready"
    assert restored.selected_joint == 2
    assert restored.viewer_connected is True


def test_runtime_uses_mjpython_for_embedded_viewport_process() -> None:
    runtime = __import__(
        "physical_ai_sandbox.ui.control_panel",
        fromlist=["ControlPanelRuntime"],
    ).ControlPanelRuntime(show_viewer=True)

    command = runtime._build_simulation_command("127.0.0.1", 12345, "00")

    assert command[:3] == [command[0], "run", "mjpython"]
    assert "physical_ai_sandbox.ui.simulation_process" in command


def test_runtime_no_viewport_uses_current_python() -> None:
    runtime = __import__(
        "physical_ai_sandbox.ui.control_panel",
        fromlist=["ControlPanelRuntime"],
    ).ControlPanelRuntime(show_viewer=False)

    command = runtime._build_simulation_command("127.0.0.1", 12345, "00")

    assert command[1] == "-m"
    assert "physical_ai_sandbox.ui.simulation_process" in command
    assert "--no-viewer" in command


def test_gui_action_mapper_emergency_stop_zeros_pending_action() -> None:
    mapper = GuiActionMapper(step_size=1.0)

    mapper.apply(PanelCommand("x_positive"))
    event = mapper.apply(PanelCommand("emergency_stop"))
    action = mapper.consume_action()

    assert event == "emergency stop"
    assert action == [0.0] * 7 + [-1.0]


def test_runtime_snapshot_preserves_viewport_connection_flag() -> None:
    runtime = __import__(
        "physical_ai_sandbox.ui.control_panel",
        fromlist=["ControlPanelRuntime"],
    ).ControlPanelRuntime(show_viewer=False)

    runtime._handle_message(ControlPanelSnapshot(viewer_connected=False).to_message())

    assert runtime.state_store.snapshot().viewer_connected is False


def test_runtime_stores_embedded_viewport_frame() -> None:
    runtime = __import__(
        "physical_ai_sandbox.ui.control_panel",
        fromlist=["ControlPanelRuntime"],
    ).ControlPanelRuntime(show_viewer=True)
    frame = b"P6\n1 1\n255\n\x00\x01\x02"

    runtime._handle_message(
        {
            "type": "frame",
            "sequence": 7,
            "ppm": base64.b64encode(frame).decode("ascii"),
            "metadata": {"fps": 30.0, "camera": {"distance": 1.2}},
        },
    )

    assert runtime.latest_frame() == (7, frame)
    assert runtime.latest_frame_metadata()["fps"] == 30.0


def test_panel_command_allows_structured_camera_payload() -> None:
    command = PanelCommand("camera_orbit", {"dx": 12, "dy": -4})

    restored = PanelCommand.from_message(command.to_message())

    assert restored.name == "camera_orbit"
    assert restored.value == {"dx": 12, "dy": -4}


def test_rgb_to_ppm_encodes_tk_photoimage_compatible_frame() -> None:
    from physical_ai_sandbox.ui.simulation_process import rgb_to_ppm

    frame = np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.uint8)

    assert rgb_to_ppm(frame) == b"P6\n2 1\n255\n\x01\x02\x03\x04\x05\x06"


def test_embedded_viewport_resize_respects_framebuffer_limit() -> None:
    from physical_ai_sandbox.ui.simulation_process import EmbeddedViewportRenderer

    created_sizes: list[tuple[int, int]] = []

    class FakeRenderer:
        def close(self) -> None:
            return None

    class FakeMujoco:
        @staticmethod
        def Renderer(_model: object, *, height: int, width: int) -> FakeRenderer:
            created_sizes.append((width, height))
            return FakeRenderer()

    renderer = EmbeddedViewportRenderer.__new__(EmbeddedViewportRenderer)
    renderer.model = SimpleNamespace(
        vis=SimpleNamespace(global_=SimpleNamespace(offwidth=1280, offheight=960)),
    )
    renderer.width = 720
    renderer.height = 480
    renderer._renderer = FakeRenderer()
    renderer._mujoco = FakeMujoco()
    renderer.dirty = False

    renderer.resize(2000, 1200)

    assert renderer.width == 1280
    assert renderer.height == 960
    assert created_sizes == [(1280, 960)]
    assert renderer.dirty is True
