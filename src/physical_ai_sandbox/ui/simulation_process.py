from __future__ import annotations

import argparse
import contextlib
import sys
import time
import traceback
from multiprocessing.connection import Client
from pathlib import Path
from typing import Any

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
    return parser


def send_snapshot(conn: Any, snapshot: ControlPanelSnapshot) -> None:
    conn.send(snapshot.to_message())


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
    viewer: Any,
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
        if viewer is not None:
            viewer.cam.azimuth = 135
            viewer.cam.elevation = -25
            viewer.cam.distance = 1.35
            viewer.cam.lookat[:] = [0.45, 0.0, 0.55]
        return running, paused, episode, step, "camera reset"
    mapper_event = mapper.apply(command)
    return running, paused, episode, step, mapper_event or last_event


def _update_viewer_overlay(
    viewer: Any,
    selected_joint: int | None,
    running: bool,
    paused: bool,
    episode: int,
    step: int,
    reward: float,
) -> None:
    text = [
        "Physical AI Sandbox",
        f"Simulation: {'Running' if running and not paused else 'Paused'}",
        f"Episode: {episode}  Step: {step}",
        f"Reward: {reward:.3f}",
        "Selected: -" if selected_joint is None else f"Selected: J{selected_joint + 1}",
    ]
    setter = getattr(viewer, "set_texts", None)
    if setter is None:
        return
    with contextlib.suppress(Exception):
        setter(text)


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
        if show_viewer:
            import mujoco.viewer

            viewer_context = mujoco.viewer.launch_passive(env.model, env.data)
        else:
            viewer_context = contextlib.nullcontext(None)

        with viewer_context as viewer:
            while True:
                if viewer is not None and not viewer.is_running():
                    last_event = "viewer closed"
                    break
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
                        viewer,
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
                        viewer_connected=viewer is not None and viewer.is_running(),
                    ),
                )
                if viewer is not None:
                    _update_viewer_overlay(
                        viewer, selected_joint, running, paused, episode, step, reward
                    )
                    viewer.sync()
                time.sleep(env.dt)
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
