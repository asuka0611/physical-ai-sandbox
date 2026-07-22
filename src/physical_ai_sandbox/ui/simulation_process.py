from __future__ import annotations

import argparse
import base64
import contextlib
import sys
import time
import traceback
from dataclasses import dataclass
from multiprocessing.connection import Client
from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH
from physical_ai_sandbox.ui.control_types import ControlPanelSnapshot, GuiActionMapper, PanelCommand
from physical_ai_sandbox.ui.i18n import normalize_language
from physical_ai_sandbox.viewer_runtime import require_mjpython_on_macos


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Physical AI Sandbox simulation process.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--authkey", required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--language", default="ja")
    parser.add_argument("--no-viewer", action="store_true")
    parser.add_argument("--render-width", type=int, default=720)
    parser.add_argument("--render-height", type=int, default=480)
    parser.add_argument("--render-fps", type=float, default=12.0)
    return parser


def send_snapshot(conn: Any, snapshot: ControlPanelSnapshot) -> None:
    conn.send(snapshot.to_message())


def send_frame(conn: Any, sequence: int, ppm: bytes) -> None:
    conn.send(
        {
            "type": "frame",
            "sequence": sequence,
            "ppm": base64.b64encode(ppm).decode("ascii"),
        },
    )


def send_error(conn: Any, message: str, traceback_text: str) -> None:
    conn.send(
        {
            "type": "error",
            "message": message,
            "traceback": traceback_text,
        },
    )


def handle_runtime_command(
    command: PanelCommand,
    env: Any,
    renderer: Any,
    mapper: GuiActionMapper,
    running: bool,
    paused: bool,
    episode: int,
    step: int,
    last_event: str,
) -> tuple[bool, bool, int, int, str]:
    if command.name == "quit":
        return False, True, episode, step, "quit"
    if command.name == "start":
        return True, False, episode, step, "start"
    if command.name == "pause":
        return running, True, episode, step, "paused"
    if command.name == "resume":
        return True, False, episode, step, "resumed"
    if command.name == "toggle_pause":
        return True, not paused, episode, step, "paused" if not paused else "resumed"
    if command.name == "reset":
        env.reset()
        return running, paused, episode + 1, 0, "reset"
    if command.name == "start_recording":
        if not env.recorder.is_recording:
            env.start_recording({"mode": "control_panel"})
        return running, paused, episode, step, "recording started"
    if command.name == "stop_recording":
        if env.recorder.is_recording:
            env.stop_recording({"mode": "control_panel"})
        return running, paused, episode, step, "recording stopped"
    if command.name == "toggle_recording":
        if env.recorder.is_recording:
            env.stop_recording({"mode": "control_panel"})
            return running, paused, episode, step, "recording stopped"
        env.start_recording({"mode": "control_panel"})
        return running, paused, episode, step, "recording started"
    if command.name == "emergency_stop":
        mapper.clear()
        return False, True, episode, step, "emergency stop"
    if command.name == "reload_scene":
        env.reset()
        return False, True, episode + 1, 0, "scene reloaded"
    if command.name == "reset_camera":
        if renderer is not None:
            renderer.reset_camera()
        return running, paused, episode, step, "camera reset"
    mapper_event = mapper.apply(command)
    return running, paused, episode, step, mapper_event or last_event


def rgb_to_ppm(rgb: np.ndarray) -> bytes:
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError(f"RGB frame must have shape (H, W, 3), got {rgb.shape}")
    height, width, _channels = rgb.shape
    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    return header + np.ascontiguousarray(rgb, dtype=np.uint8).tobytes()


@dataclass
class EmbeddedViewportRenderer:
    model: Any
    width: int
    height: int

    def __post_init__(self) -> None:
        import mujoco

        self._mujoco = mujoco
        self._renderer = mujoco.Renderer(self.model, height=self.height, width=self.width)
        self._camera = mujoco.MjvCamera()
        self.reset_camera()

    def reset_camera(self) -> None:
        self._camera.azimuth = 135
        self._camera.elevation = -25
        self._camera.distance = 1.35
        self._camera.lookat[:] = [0.45, 0.0, 0.55]

    def render_ppm(self, data: Any) -> bytes:
        self._renderer.update_scene(data, camera=self._camera)
        return rgb_to_ppm(self._renderer.render())

    def close(self) -> None:
        self._renderer.close()


def run_simulation(args: argparse.Namespace) -> int:
    show_viewer = not args.no_viewer
    if show_viewer:
        require_mjpython_on_macos()

    conn = Client((args.host, args.port), authkey=bytes.fromhex(args.authkey))
    env = None
    try:
        from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv

        env = PandaPickPlaceEnv(args.config)
        max_steps = max(1, int(env.evaluator.time_limit_seconds / env.dt))
        running = False
        paused = True
        episode = 1
        step = 0
        reward = 0.0
        last_event = "ready"
        selected_joint: int | None = None
        mapper = GuiActionMapper()
        language = normalize_language(args.language)
        renderer = (
            EmbeddedViewportRenderer(env.model, width=args.render_width, height=args.render_height)
            if show_viewer
            else None
        )
        frame_sequence = 0
        frame_period = 1.0 / max(1.0, float(args.render_fps))
        last_frame_time = 0.0
        try:
            while True:
                while conn.poll(0):
                    message = conn.recv()
                    if not isinstance(message, dict):
                        continue
                    if message.get("type") != "command":
                        continue
                    command = PanelCommand.from_message(message)
                    if command.name == "select_joint" and command.value is not None:
                        index = int(command.value)
                        if 0 <= index < 7:
                            selected_joint = index
                            last_event = f"selected J{index + 1}"
                        else:
                            last_event = "invalid joint selection"
                        continue
                    if command.name == "next_joint":
                        selected_joint = 0 if selected_joint is None else (selected_joint + 1) % 7
                        last_event = f"selected J{selected_joint + 1}"
                        continue
                    if command.name == "previous_joint":
                        selected_joint = 6 if selected_joint is None else (selected_joint - 1) % 7
                        last_event = f"selected J{selected_joint + 1}"
                        continue
                    if command.name == "quit":
                        last_event = "quit"
                        raise KeyboardInterrupt
                    running, paused, episode, step, last_event = handle_runtime_command(
                        command,
                        env,
                        renderer,
                        mapper,
                        running,
                        paused,
                        episode,
                        step,
                        last_event,
                    )
                if running and not paused:
                    observation, reward, terminated, truncated, _info = env.step(
                        mapper.consume_action(),
                    )
                    step += 1
                    lifted = observation["cube_position"][2] > env.evaluator.table_top_z + 0.05
                    if terminated or truncated or step >= max_steps:
                        last_event = "success" if observation["is_success"] else "failure"
                        episode += 1
                        step = 0
                        env.reset()
                else:
                    observation = env._observation()
                    lifted = observation["cube_position"][2] > env.evaluator.table_top_z + 0.05
                send_snapshot(
                    conn,
                    ControlPanelSnapshot(
                        running=running,
                        paused=paused,
                        episode=episode,
                        step=step,
                        max_steps=max_steps,
                        reward=reward,
                        grasped=bool(observation["is_grasped"]),
                        lifted=bool(lifted),
                        success=bool(observation["is_success"]),
                        recording=env.recorder.is_recording,
                        language=language,
                        last_event=last_event,
                        selected_joint=selected_joint,
                        viewer_connected=renderer is not None,
                    ),
                )
                now = time.monotonic()
                if renderer is not None and now - last_frame_time >= frame_period:
                    send_frame(conn, frame_sequence, renderer.render_ppm(env.data))
                    frame_sequence += 1
                    last_frame_time = now
                time.sleep(env.dt)
        finally:
            if renderer is not None:
                renderer.close()
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        traceback_text = "".join(traceback.format_exception(exc))
        with contextlib.suppress(Exception):
            send_error(conn, str(exc), traceback_text)
        print(traceback_text, file=sys.stderr)
        return 1
    finally:
        if env is not None:
            env.close()
        with contextlib.suppress(Exception):
            conn.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    return run_simulation(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
