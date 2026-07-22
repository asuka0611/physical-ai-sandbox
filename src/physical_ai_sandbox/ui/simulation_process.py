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
    parser.add_argument("--render-fps", type=float, default=30.0)
    return parser


def send_snapshot(conn: Any, snapshot: ControlPanelSnapshot) -> None:
    conn.send(snapshot.to_message())


def send_frame(
    conn: Any,
    sequence: int,
    ppm: bytes,
    metadata: dict[str, object] | None = None,
) -> None:
    conn.send(
        {
            "type": "frame",
            "sequence": sequence,
            "ppm": base64.b64encode(ppm).decode("ascii"),
            "metadata": metadata or {},
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
    if renderer is not None and command.name.startswith("camera_"):
        return running, paused, episode, step, renderer.apply_command(command)
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

    def apply_command(self, command: PanelCommand) -> str:
        value = command.value if isinstance(command.value, dict) else {}
        if command.name == "camera_orbit":
            self.orbit(float(value.get("dx", 0.0)), float(value.get("dy", 0.0)))
            return "camera orbit"
        if command.name == "camera_pan":
            self.pan(float(value.get("dx", 0.0)), float(value.get("dy", 0.0)))
            return "camera pan"
        if command.name == "camera_zoom":
            self.zoom(float(value.get("delta", 0.0)))
            return "camera zoom"
        if command.name == "camera_preset":
            self.set_preset(str(value.get("name", "isometric")))
            return f"camera {value.get('name', 'isometric')}"
        if command.name == "camera_focus":
            target = value.get("target")
            if isinstance(target, list | tuple) and len(target) == 3:
                self._camera.lookat[:] = [float(item) for item in target]
            return "camera focus"
        if command.name == "camera_state":
            self.set_state(value)
            return "camera state restored"
        if command.name == "camera_viewport_size":
            self.resize(int(value.get("width", self.width)), int(value.get("height", self.height)))
            return "viewport resized"
        return "camera command"

    def state(self) -> dict[str, object]:
        return {
            "azimuth": float(self._camera.azimuth),
            "elevation": float(self._camera.elevation),
            "distance": float(self._camera.distance),
            "lookat": [float(item) for item in self._camera.lookat],
        }

    def set_state(self, state: dict[str, object]) -> None:
        if "azimuth" in state:
            self._camera.azimuth = float(state["azimuth"])
        if "elevation" in state:
            self._camera.elevation = float(state["elevation"])
        if "distance" in state:
            self._camera.distance = max(0.2, min(6.0, float(state["distance"])))
        lookat = state.get("lookat")
        if isinstance(lookat, list | tuple) and len(lookat) == 3:
            self._camera.lookat[:] = [float(item) for item in lookat]

    def resize(self, width: int, height: int) -> None:
        width = int(np.clip(width, 240, 1920))
        height = int(np.clip(height, 180, 1080))
        if width == self.width and height == self.height:
            return
        self.width = width
        self.height = height
        self._renderer.close()
        self._renderer = self._mujoco.Renderer(self.model, height=self.height, width=self.width)

    def orbit(self, dx: float, dy: float) -> None:
        self._camera.azimuth = float((self._camera.azimuth - dx * 0.35) % 360.0)
        self._camera.elevation = float(np.clip(self._camera.elevation + dy * 0.25, -89.0, 89.0))

    def pan(self, dx: float, dy: float) -> None:
        forward, right, up = self._camera_basis()
        scale = max(0.0008, float(self._camera.distance) * 0.0015)
        del forward
        self._camera.lookat[:] = self._camera.lookat + right * (-dx * scale) + up * (dy * scale)

    def zoom(self, delta: float) -> None:
        factor = 0.90 if delta > 0 else 1.10
        steps = max(1, min(8, int(abs(delta))))
        self._camera.distance = float(np.clip(self._camera.distance * (factor**steps), 0.2, 6.0))

    def set_preset(self, name: str) -> None:
        presets = {
            "front": (180.0, 0.0),
            "back": (0.0, 0.0),
            "right": (90.0, 0.0),
            "left": (270.0, 0.0),
            "top": (135.0, -89.0),
            "bottom": (135.0, 89.0),
            "isometric": (135.0, -25.0),
        }
        azimuth, elevation = presets.get(name, presets["isometric"])
        self._camera.azimuth = azimuth
        self._camera.elevation = elevation

    def focus_joint(self, data: Any, joint_index: int) -> None:
        site_name = f"joint{joint_index + 1}_label_site"
        site_id = self._mujoco.mj_name2id(self.model, self._mujoco.mjtObj.mjOBJ_SITE, site_name)
        if site_id >= 0:
            self._camera.lookat[:] = np.asarray(data.site_xpos[site_id], dtype=float)

    def render_ppm(self, data: Any) -> bytes:
        self._renderer.update_scene(data, camera=self._camera)
        return rgb_to_ppm(self._renderer.render())

    def frame_metadata(
        self,
        data: Any,
        selected_joint: int | None,
        fps: float,
        simulation_hz: float,
    ) -> dict[str, object]:
        return {
            "camera": self.state(),
            "joint_labels": self.joint_labels(data, selected_joint),
            "fps": fps,
            "simulation_hz": simulation_hz,
            "render_size": {"width": self.width, "height": self.height},
        }

    def joint_labels(self, data: Any, selected_joint: int | None) -> list[dict[str, object]]:
        labels: list[dict[str, object]] = []
        for index in range(7):
            site_name = f"joint{index + 1}_label_site"
            site_id = self._mujoco.mj_name2id(self.model, self._mujoco.mjtObj.mjOBJ_SITE, site_name)
            if site_id < 0:
                continue
            point = np.array(data.site_xpos[site_id], dtype=float)
            projected = self.project_world(point)
            if projected is None:
                continue
            labels.append(
                {
                    "joint": index,
                    "name": f"J{index + 1}",
                    "x": projected[0],
                    "y": projected[1],
                    "selected": selected_joint == index,
                    "world": [float(item) for item in point],
                },
            )
        return labels

    def project_world(self, point: np.ndarray) -> tuple[float, float] | None:
        forward, right, up = self._camera_basis()
        camera_pos = np.asarray(self._camera.lookat, dtype=float) - forward * float(
            self._camera.distance,
        )
        rel = point - camera_pos
        depth = float(np.dot(rel, forward))
        if depth <= 1e-6:
            return None
        x_coord = float(np.dot(rel, right))
        y_coord = float(np.dot(rel, up))
        fovy = float(getattr(self.model.vis.global_, "fovy", 45.0))
        focal = (self.height / 2.0) / np.tan(np.deg2rad(fovy) / 2.0)
        x = self.width / 2.0 + focal * x_coord / depth
        y = self.height / 2.0 - focal * y_coord / depth
        if x < -80 or x > self.width + 80 or y < -80 or y > self.height + 80:
            return None
        return float(x), float(y)

    def _camera_basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        azimuth = np.deg2rad(float(self._camera.azimuth))
        elevation = np.deg2rad(float(self._camera.elevation))
        forward = np.array(
            [
                np.cos(elevation) * np.cos(azimuth),
                np.cos(elevation) * np.sin(azimuth),
                np.sin(elevation),
            ],
            dtype=float,
        )
        forward /= max(1e-9, np.linalg.norm(forward))
        world_up = np.array([0.0, 0.0, 1.0], dtype=float)
        right = np.cross(forward, world_up)
        if np.linalg.norm(right) < 1e-6:
            right = np.array([1.0, 0.0, 0.0], dtype=float)
        right /= max(1e-9, np.linalg.norm(right))
        up = np.cross(right, forward)
        up /= max(1e-9, np.linalg.norm(up))
        return forward, right, up

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
        measured_fps = 0.0
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
                            if renderer is not None:
                                renderer.focus_joint(env.data, selected_joint)
                            last_event = f"selected J{index + 1}"
                        else:
                            last_event = "invalid joint selection"
                        continue
                    if command.name == "next_joint":
                        selected_joint = 0 if selected_joint is None else (selected_joint + 1) % 7
                        if renderer is not None:
                            renderer.focus_joint(env.data, selected_joint)
                        last_event = f"selected J{selected_joint + 1}"
                        continue
                    if command.name == "previous_joint":
                        selected_joint = 6 if selected_joint is None else (selected_joint - 1) % 7
                        if renderer is not None:
                            renderer.focus_joint(env.data, selected_joint)
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
                    if last_frame_time > 0:
                        measured_fps = 1.0 / max(1e-6, now - last_frame_time)
                    send_frame(
                        conn,
                        frame_sequence,
                        renderer.render_ppm(env.data),
                        renderer.frame_metadata(
                            env.data,
                            selected_joint,
                            measured_fps,
                            1.0 / max(env.dt, 1e-9),
                        ),
                    )
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
