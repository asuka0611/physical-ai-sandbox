from __future__ import annotations

import time
from contextlib import nullcontext
from dataclasses import dataclass, replace
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Any

import numpy as np

from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH
from physical_ai_sandbox.scene.config import load_and_validate_config
from physical_ai_sandbox.ui.i18n import Language, normalize_language, translate
from physical_ai_sandbox.viewer_runtime import require_mjpython_on_macos


@dataclass(frozen=True, slots=True)
class PanelCommand:
    name: str
    value: str | float | int | None = None


class ControlCommandQueue:
    def __init__(self) -> None:
        self._queue: Queue[PanelCommand] = Queue()

    def put(self, name: str, value: str | float | int | None = None) -> None:
        self._queue.put(PanelCommand(name=name, value=value))

    def drain(self) -> list[PanelCommand]:
        commands: list[PanelCommand] = []
        while True:
            try:
                commands.append(self._queue.get_nowait())
            except Empty:
                return commands


@dataclass(frozen=True, slots=True)
class ControlPanelSnapshot:
    app_name: str = "Physical AI Sandbox"
    running: bool = False
    paused: bool = True
    episode: int = 1
    step: int = 0
    max_steps: int = 0
    reward: float = 0.0
    grasped: bool = False
    lifted: bool = False
    success: bool = False
    recording: bool = False
    controller: str = "Manual Control"
    environment: str = "panda_pick_place"
    language: Language = "ja"
    last_event: str = "ready"


class ControlPanelStateStore:
    def __init__(self, initial: ControlPanelSnapshot | None = None) -> None:
        self._snapshot = initial or ControlPanelSnapshot()
        self._lock = Lock()

    def snapshot(self) -> ControlPanelSnapshot:
        with self._lock:
            return self._snapshot

    def update(self, **changes: Any) -> ControlPanelSnapshot:
        with self._lock:
            self._snapshot = replace(self._snapshot, **changes)
            return self._snapshot


class GuiActionMapper:
    _ACTION_PRESETS: dict[str, tuple[float, float, float, float, float, float, float]] = {
        "x_positive": (0.0, -0.45, 0.0, 0.55, 0.0, 0.20, 0.0),
        "x_negative": (0.0, 0.45, 0.0, -0.55, 0.0, -0.20, 0.0),
        "y_positive": (0.70, 0.0, 0.20, 0.0, 0.0, 0.0, 0.0),
        "y_negative": (-0.70, 0.0, -0.20, 0.0, 0.0, 0.0, 0.0),
        "z_positive": (0.0, -0.55, 0.0, -0.35, 0.0, 0.45, 0.0),
        "z_negative": (0.0, 0.55, 0.0, 0.35, 0.0, -0.45, 0.0),
        "rotate_positive": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.75),
        "rotate_negative": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.75),
    }

    def __init__(self, step_size: float = 0.8) -> None:
        self.step_size = step_size
        self.gripper_closed = False
        self._pending = np.zeros(7, dtype=float)

    def apply(self, command: PanelCommand) -> str | None:
        if command.name == "set_step_size" and command.value is not None:
            self.step_size = float(np.clip(float(command.value), 0.1, 1.0))
            return f"step size {self.step_size:.2f}"
        if command.name == "open_gripper":
            self.gripper_closed = False
            return "gripper open"
        if command.name == "close_gripper":
            self.gripper_closed = True
            return "gripper closed"
        if command.name in self._ACTION_PRESETS:
            preset = np.array(self._ACTION_PRESETS[command.name], dtype=float)
            self._pending += preset * self.step_size
            return command.name
        if command.name in {"joint_positive", "joint_negative"} and command.value is not None:
            index = int(command.value)
            if not 0 <= index < 7:
                raise ValueError(f"Joint index must be 0..6, got {index}")
            direction = 1.0 if command.name == "joint_positive" else -1.0
            self._pending[index] += direction * self.step_size
            return f"joint {index + 1} {'positive' if direction > 0 else 'negative'}"
        return None

    def consume_action(self) -> list[float]:
        action = np.zeros(8, dtype=float)
        action[:7] = np.clip(self._pending, -1.0, 1.0)
        action[7] = 1.0 if self.gripper_closed else -1.0
        self._pending[:] = 0.0
        return action.tolist()


class ControlPanelRuntime:
    def __init__(
        self,
        *,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        command_queue: ControlCommandQueue | None = None,
        state_store: ControlPanelStateStore | None = None,
        language: str = "ja",
        show_viewer: bool = True,
    ) -> None:
        self.config_path = Path(config_path)
        self.command_queue = command_queue or ControlCommandQueue()
        self.state_store = state_store or ControlPanelStateStore(
            ControlPanelSnapshot(language=normalize_language(language)),
        )
        self.language = normalize_language(language)
        self.show_viewer = show_viewer
        self.stop_event = Event()
        self._thread: Thread | None = None
        self._mapper = GuiActionMapper()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = Thread(target=self._run, name="physical-ai-control-panel-sim")
        self._thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.command_queue.put("quit")

    def join(self, timeout: float = 5.0) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        if self.show_viewer:
            require_mjpython_on_macos()

        from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv

        env = PandaPickPlaceEnv(self.config_path)
        max_steps = max(1, int(env.evaluator.time_limit_seconds / env.dt))
        running = False
        paused = True
        episode = 1
        step = 0
        reward = 0.0
        last_event = "ready"
        if self.show_viewer:
            import mujoco.viewer

            viewer_context = mujoco.viewer.launch_passive(env.model, env.data)
        else:
            viewer_context = nullcontext(None)
        try:
            with viewer_context as viewer:
                while not self.stop_event.is_set():
                    if viewer is not None and not viewer.is_running():
                        self.stop_event.set()
                        break
                    for command in self.command_queue.drain():
                        (
                            running,
                            paused,
                            episode,
                            step,
                            last_event,
                        ) = self._handle_runtime_command(
                            command,
                            env,
                            viewer,
                            running,
                            paused,
                            episode,
                            step,
                            last_event,
                        )
                    if running and not paused:
                        observation, reward, terminated, truncated, _info = env.step(
                            self._mapper.consume_action(),
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
                    self.state_store.update(
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
                        language=self.language,
                        last_event=last_event,
                    )
                    if viewer is not None:
                        viewer.sync()
                    time.sleep(env.dt)
        finally:
            env.close()
            self.state_store.update(
                running=False,
                paused=True,
                recording=False,
                last_event="stopped",
            )

    def _handle_runtime_command(
        self,
        command: PanelCommand,
        env: Any,
        viewer: Any,
        running: bool,
        paused: bool,
        episode: int,
        step: int,
        last_event: str,
    ) -> tuple[bool, bool, int, int, str]:
        if command.name == "quit":
            self.stop_event.set()
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
        if command.name == "reset_camera":
            if viewer is not None:
                viewer.cam.azimuth = 135
                viewer.cam.elevation = -25
                viewer.cam.distance = 1.35
                viewer.cam.lookat[:] = [0.45, 0.0, 0.55]
            return running, paused, episode, step, "camera reset"
        mapper_event = self._mapper.apply(command)
        return running, paused, episode, step, mapper_event or last_event


class TkControlPanel:
    def __init__(self, runtime: ControlPanelRuntime) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.runtime = runtime
        self.command_queue = runtime.command_queue
        self.state_store = runtime.state_store
        self.root = tk.Tk()
        self.root.title("Physical AI Sandbox")
        self.root.configure(bg="#20242a")
        self.language_var = tk.StringVar(value=self.state_store.snapshot().language)
        self.step_size_var = tk.DoubleVar(value=0.8)
        self.status_vars: dict[str, Any] = {}
        self.buttons: dict[str, Any] = {}
        self.labels: dict[str, Any] = {}
        self._build()
        self._bind_keys()
        self._refresh()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def run(self) -> None:
        self.runtime.start()
        self.root.mainloop()
        self.runtime.stop()
        self.runtime.join()

    def close(self) -> None:
        self.runtime.stop()
        self.root.after(100, self.root.destroy)

    def _build(self) -> None:
        tk = self.tk
        ttk = self.ttk
        frame = tk.Frame(self.root, bg="#20242a", padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        title = tk.Label(
            frame,
            text="Physical AI Sandbox",
            bg="#20242a",
            fg="#f4f7fb",
            font=("Helvetica", 18, "bold"),
        )
        title.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 12))

        self.labels["language"] = tk.Label(frame, bg="#20242a", fg="#cbd5e1")
        self.labels["language"].grid(row=1, column=0, sticky="w")
        language_menu = ttk.OptionMenu(
            frame,
            self.language_var,
            self.language_var.get(),
            "ja",
            "en",
            command=self._set_language,
        )
        language_menu.grid(row=1, column=1, sticky="ew", pady=2)

        status_frame = tk.LabelFrame(frame, bg="#20242a", fg="#f4f7fb", padx=10, pady=8)
        status_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(8, 12))
        self.labels["experiment_status"] = status_frame
        for index, key in enumerate(
            [
                "episode",
                "step",
                "reward",
                "grasped",
                "lifted",
                "success",
                "recording",
                "controller",
                "last_event",
            ],
        ):
            label = tk.Label(status_frame, bg="#20242a", fg="#94a3b8")
            label.grid(row=index // 3, column=(index % 3) * 2, sticky="w", padx=(0, 6), pady=2)
            value = tk.StringVar(value="-")
            value_label = tk.Label(status_frame, textvariable=value, bg="#20242a", fg="#f8fafc")
            value_label.grid(row=index // 3, column=(index % 3) * 2 + 1, sticky="w", padx=(0, 16))
            self.labels[key] = label
            self.status_vars[key] = value

        controls = tk.Frame(frame, bg="#20242a")
        controls.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(0, 12))
        for index, command in enumerate(
            [
                "start",
                "toggle_pause",
                "reset",
                "toggle_recording",
                "open_gripper",
                "close_gripper",
                "reset_camera",
                "quit",
            ],
        ):
            button = ttk.Button(
                controls,
                command=lambda name=command: self._send(name),
            )
            button.grid(row=index // 4, column=index % 4, padx=3, pady=3, sticky="ew")
            self.buttons[command] = button

        move_frame = tk.LabelFrame(frame, bg="#20242a", fg="#f4f7fb", padx=10, pady=8)
        move_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=(0, 8))
        self.labels["xyz_control"] = move_frame
        move_buttons = [
            ("x_positive", "+X", 0, 1),
            ("x_negative", "-X", 2, 1),
            ("y_positive", "+Y", 1, 2),
            ("y_negative", "-Y", 1, 0),
            ("z_positive", "+Z", 0, 3),
            ("z_negative", "-Z", 2, 3),
            ("rotate_negative", "-R", 0, 4),
            ("rotate_positive", "+R", 2, 4),
        ]
        for command, text, row, column in move_buttons:
            button = ttk.Button(
                move_frame,
                text=text,
                command=lambda name=command: self._send(name),
            )
            button.grid(row=row, column=column, padx=3, pady=3, sticky="ew")
            self.buttons[command] = button

        joints_frame = tk.LabelFrame(frame, bg="#20242a", fg="#f4f7fb", padx=10, pady=8)
        joints_frame.grid(row=4, column=2, columnspan=2, sticky="nsew")
        self.labels["joints"] = joints_frame
        for index in range(7):
            tk.Label(joints_frame, text=f"J{index + 1}", bg="#20242a", fg="#cbd5e1").grid(
                row=index,
                column=0,
                padx=(0, 5),
                pady=1,
            )
            ttk.Button(
                joints_frame,
                text="-",
                width=3,
                command=lambda joint=index: self._send("joint_negative", joint),
            ).grid(row=index, column=1, padx=2, pady=1)
            ttk.Button(
                joints_frame,
                text="+",
                width=3,
                command=lambda joint=index: self._send("joint_positive", joint),
            ).grid(row=index, column=2, padx=2, pady=1)

        self.labels["step_size"] = tk.Label(frame, bg="#20242a", fg="#cbd5e1")
        self.labels["step_size"].grid(row=5, column=0, sticky="w", pady=(10, 0))
        scale = ttk.Scale(
            frame,
            variable=self.step_size_var,
            from_=0.1,
            to=1.0,
            command=lambda value: self._send("set_step_size", float(value)),
        )
        scale.grid(row=5, column=1, columnspan=3, sticky="ew", pady=(10, 0))

        help_frame = tk.LabelFrame(frame, bg="#20242a", fg="#f4f7fb", padx=10, pady=8)
        help_frame.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        self.labels["keyboard_help"] = help_frame
        self.help_text = tk.StringVar(value="")
        tk.Label(
            help_frame,
            textvariable=self.help_text,
            justify="left",
            bg="#20242a",
            fg="#dbeafe",
        ).pack(anchor="w")

        for column in range(4):
            frame.grid_columnconfigure(column, weight=1)

        self._render_text()

    def _bind_keys(self) -> None:
        bindings = {
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
            "<space>": "toggle_pause",
            "<Return>": "reset",
            "<Escape>": "quit",
        }
        for key, command in bindings.items():
            self.root.bind(key, lambda _event, name=command: self._send(name))

    def _send(self, name: str, value: str | float | int | None = None) -> None:
        if name == "quit":
            self.close()
            return
        self.command_queue.put(name, value)

    def _set_language(self, language: str) -> None:
        normalized = normalize_language(language)
        self.runtime.language = normalized
        self.state_store.update(language=normalized)
        self._render_text()

    def _render_text(self) -> None:
        language = self.language_var.get()
        for key, widget in self.labels.items():
            widget.configure(text=translate(key, language))
        button_keys = {
            "start": "start",
            "toggle_pause": "pause",
            "reset": "reset",
            "toggle_recording": "start_recording",
            "open_gripper": "open_gripper",
            "close_gripper": "close_gripper",
            "reset_camera": "reset_camera",
            "quit": "quit",
        }
        for command, key in button_keys.items():
            self.buttons[command].configure(text=translate(key, language))
        self.help_text.set(self._help_text(language))

    def _refresh(self) -> None:
        snapshot = self.state_store.snapshot()
        language = snapshot.language
        if self.language_var.get() != language:
            self.language_var.set(language)
            self._render_text()
        state_key = "running" if snapshot.running and not snapshot.paused else "paused"
        if not snapshot.running:
            state_key = "ready"
        self.status_vars["episode"].set(str(snapshot.episode))
        self.status_vars["step"].set(f"{snapshot.step} / {snapshot.max_steps}")
        self.status_vars["reward"].set(f"{snapshot.reward:.3f}")
        self.status_vars["grasped"].set(self._bool_text(snapshot.grasped, language))
        self.status_vars["lifted"].set(self._bool_text(snapshot.lifted, language))
        self.status_vars["success"].set(self._bool_text(snapshot.success, language))
        self.status_vars["recording"].set(self._bool_text(snapshot.recording, language))
        self.status_vars["controller"].set(translate("manual_control", language))
        self.status_vars["last_event"].set(
            f"{translate(state_key, language)} / {snapshot.last_event}",
        )
        self.buttons["toggle_pause"].configure(
            text=translate("resume" if snapshot.paused else "pause", language),
        )
        self.buttons["toggle_recording"].configure(
            text=translate("stop_recording" if snapshot.recording else "start_recording", language),
        )
        self.root.after(100, self._refresh)

    @staticmethod
    def _bool_text(value: bool, language: str) -> str:
        return translate("yes" if value else "no", language)

    @staticmethod
    def _help_text(language: str) -> str:
        if normalize_language(language) == "ja":
            return "\n".join(
                [
                    "W / S: 前後",
                    "A / D: 左右",
                    "R / F: 上下",
                    "Q / E: 回転",
                    "O: グリッパーを開く",
                    "C: グリッパーを閉じる",
                    "Space: 一時停止 / 再開",
                    "Enter: リセット",
                    "Esc: 終了",
                ],
            )
        return "\n".join(
            [
                "W / S: forward / backward",
                "A / D: left / right",
                "R / F: up / down",
                "Q / E: rotate",
                "O: open gripper",
                "C: close gripper",
                "Space: pause / resume",
                "Enter: reset",
                "Esc: quit",
            ],
        )


def run_control_panel(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    language: str | None = None,
    show_viewer: bool = True,
) -> None:
    config = load_and_validate_config(config_path)
    selected_language = language or config["ui"]["language"]
    runtime = ControlPanelRuntime(
        config_path=config_path,
        language=selected_language,
        show_viewer=show_viewer,
    )
    TkControlPanel(runtime).run()
