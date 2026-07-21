from __future__ import annotations

import contextlib
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
import traceback
from dataclasses import replace
from datetime import UTC, datetime
from multiprocessing.connection import Connection, Listener
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Any

from physical_ai_sandbox.app.paths import build_app_paths
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH
from physical_ai_sandbox.scene.config import load_and_validate_config
from physical_ai_sandbox.ui.control_types import ControlPanelSnapshot, PanelCommand
from physical_ai_sandbox.ui.i18n import normalize_language, translate


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

    def replace(self, snapshot: ControlPanelSnapshot) -> ControlPanelSnapshot:
        with self._lock:
            self._snapshot = snapshot
            return self._snapshot


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
        self._listener: Listener | None = None
        self._connection: Connection | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._io_thread: Thread | None = None
        self._monitor_thread: Thread | None = None
        self._log_file: Path | None = None

    def start(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        self.stop_event.clear()
        try:
            self._start_simulation_process()
        except Exception as exc:
            self._publish_startup_error(exc, traceback.format_exc())

    def stop(self) -> None:
        self.stop_event.set()
        self.command_queue.put("quit")
        self._send_quit()
        self._close_ipc()
        self._terminate_process_tree()

    def join(self, timeout: float = 5.0) -> None:
        deadline = time.monotonic() + timeout
        for thread in (self._io_thread, self._monitor_thread):
            if thread is None:
                continue
            remaining = max(0.0, deadline - time.monotonic())
            thread.join(timeout=remaining)

    def _start_simulation_process(self) -> None:
        authkey = secrets.token_bytes(16)
        listener = Listener(("127.0.0.1", 0), authkey=authkey)
        self._listener = listener
        host, port = listener.address
        app_paths = build_app_paths()
        app_paths.logs_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = app_paths.logs_dir / "control_panel_simulation.log"
        log_handle = self._log_file.open("ab")
        command = self._build_simulation_command(host, int(port), authkey.hex())
        self._process = subprocess.Popen(
            command,
            cwd=str(Path.cwd()),
            stdout=log_handle,
            stderr=log_handle,
            start_new_session=(os.name != "nt"),
        )
        log_handle.close()
        self._io_thread = Thread(target=self._io_loop, name="physical-ai-control-panel-ipc")
        self._io_thread.daemon = True
        self._io_thread.start()
        self._monitor_thread = Thread(
            target=self._monitor_process,
            name="physical-ai-control-panel-monitor",
        )
        self._monitor_thread.daemon = True
        self._monitor_thread.start()

    def _build_simulation_command(self, host: str, port: int, authkey: str) -> list[str]:
        module_args = [
            "-m",
            "physical_ai_sandbox.ui.simulation_process",
            "--host",
            host,
            "--port",
            str(port),
            "--authkey",
            authkey,
            "--config",
            str(self.config_path),
            "--language",
            self.language,
        ]
        if not self.show_viewer:
            return [sys.executable, *module_args, "--no-viewer"]
        uv_path = shutil.which("uv")
        if uv_path is None:
            raise RuntimeError("uv が見つかりません。ログインシェルの PATH を確認してください。")
        return [uv_path, "run", "mjpython", *module_args]

    def _io_loop(self) -> None:
        try:
            if self._listener is None:
                return
            connection = self._listener.accept()
            self._connection = connection
            while not self.stop_event.is_set():
                for command in self.command_queue.drain():
                    try:
                        connection.send(command.to_message())
                    except (BrokenPipeError, EOFError, OSError):
                        return
                while connection.poll(0.02):
                    message = connection.recv()
                    if isinstance(message, dict):
                        self._handle_message(message)
                time.sleep(0.02)
        except (EOFError, OSError):
            if not self.stop_event.is_set():
                self.state_store.update(running=False, paused=True, last_event="viewer stopped")
        except Exception as exc:
            if not self.stop_event.is_set():
                self._publish_startup_error(exc, traceback.format_exc())

    def _handle_message(self, message: dict[str, object]) -> None:
        message_type = message.get("type")
        if message_type == "snapshot":
            snapshot = ControlPanelSnapshot.from_message(message)
            if snapshot.language != self.language:
                snapshot = replace(snapshot, language=self.language)
            self.state_store.replace(snapshot)
            return
        if message_type == "error":
            error_message = str(message.get("message") or "Viewerを起動できませんでした。")
            traceback_text = str(message.get("traceback") or "")
            report_path = self._write_crash_report(error_message, traceback_text)
            self.state_store.update(
                running=False,
                paused=True,
                max_steps=1,
                last_event="起動失敗",
                error_message=f"{error_message}\n\nCrash report: {report_path}",
            )

    def _monitor_process(self) -> None:
        process = self._process
        if process is None:
            return
        returncode = process.wait()
        if self.stop_event.is_set():
            return
        if returncode != 0:
            self.state_store.update(
                running=False,
                paused=True,
                max_steps=1,
                last_event=f"process exited {returncode}",
                error_message=(
                    f"Viewer process exited with status {returncode}. Log: {self._log_file}"
                ),
            )
        else:
            self.state_store.update(running=False, paused=True, last_event="viewer closed")

    def _send_quit(self) -> None:
        connection = self._connection
        if connection is None:
            return
        with contextlib.suppress(BrokenPipeError, EOFError, OSError):
            connection.send(PanelCommand("quit").to_message())

    def _close_ipc(self) -> None:
        if self._connection is not None:
            with contextlib.suppress(OSError):
                self._connection.close()
            self._connection = None
        if self._listener is not None:
            with contextlib.suppress(OSError):
                self._listener.close()
            self._listener = None

    def _terminate_process_tree(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            process.wait(timeout=2.0)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            process.wait(timeout=3.0)
            return
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            try:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except ProcessLookupError:
                pass
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=1.0)

    def _publish_startup_error(self, exc: BaseException, traceback_text: str) -> None:
        report_path = self._write_crash_report(str(exc), traceback_text)
        self.state_store.update(
            running=False,
            paused=True,
            max_steps=1,
            last_event="起動失敗",
            error_message=f"{exc}\n\nCrash report: {report_path}",
        )

    def _write_crash_report(self, message: str, traceback_text: str) -> Path:
        crash_dir = build_app_paths().crash_reports_dir
        crash_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        path = crash_dir / f"control_panel_viewer_{timestamp}.log"
        path.write_text(
            "\n".join(
                [
                    "app: Physical AI Sandbox",
                    "phase: 4.6",
                    f"error: {message}",
                    f"simulation_log: {self._log_file}",
                    "traceback:",
                    traceback_text,
                ],
            ),
            encoding="utf-8",
        )
        return path



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
        self._shown_error_message: str | None = None
        self._build()
        self._bind_keys()
        self._refresh()
        self._build_menu()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def run(self) -> None:
        self.runtime.start()
        self.root.mainloop()
        self.runtime.stop()
        self.runtime.join()

    def _build_menu(self) -> None:
        menu = self.tk.Menu(self.root)
        app_menu = self.tk.Menu(menu, tearoff=False)
        app_menu.add_command(label="Physical AI Sandboxについて", command=self._show_about)
        app_menu.add_command(label="設定", command=self._open_config_folder)
        app_menu.add_command(label="ログフォルダを開く", command=self._open_logs_folder)
        app_menu.add_separator()
        app_menu.add_command(label="終了", command=self.close)
        menu.add_cascade(label="Physical AI Sandbox", menu=app_menu)

        experiment_menu = self.tk.Menu(menu, tearoff=False)
        experiment_menu.add_command(label="開始", command=lambda: self._send("start"))
        experiment_menu.add_command(label="一時停止", command=lambda: self._send("pause"))
        experiment_menu.add_command(label="リセット", command=lambda: self._send("reset"))
        experiment_menu.add_command(label="記録開始", command=lambda: self._send("start_recording"))
        experiment_menu.add_command(label="記録停止", command=lambda: self._send("stop_recording"))
        menu.add_cascade(label="実験", menu=experiment_menu)

        view_menu = self.tk.Menu(menu, tearoff=False)
        view_menu.add_command(
            label="Viewerを前面に表示",
            command=lambda: self._send("reset_camera"),
        )
        view_menu.add_command(label="操作パネルを前面に表示", command=self.root.lift)
        view_menu.add_command(label="カメラをリセット", command=lambda: self._send("reset_camera"))
        view_menu.add_separator()
        view_menu.add_command(label="日本語", command=lambda: self._set_language("ja"))
        view_menu.add_command(label="English", command=lambda: self._set_language("en"))
        menu.add_cascade(label="表示", menu=view_menu)

        help_menu = self.tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="操作ガイド", command=self._open_ui_guide)
        help_menu.add_command(label="GitHubを開く", command=self._open_github)
        help_menu.add_command(label="バージョン情報", command=self._show_about)
        menu.add_cascade(label="ヘルプ", menu=help_menu)
        self.root.config(menu=menu)

    def _show_about(self) -> None:
        from importlib.metadata import PackageNotFoundError, version
        from tkinter import messagebox

        try:
            app_version = version("physical-ai-sandbox")
        except PackageNotFoundError:
            app_version = "0.0.0"
        messagebox.showinfo(
            "Physical AI Sandboxについて",
            f"Physical AI Sandbox\nVersion {app_version}\nPhase 4.6",
        )

    def _open_path(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        if subprocess.run(["open", str(path)], check=False).returncode != 0:
            self.status_vars.get("last_event", self.tk.StringVar()).set(str(path))

    def _open_logs_folder(self) -> None:
        self._open_path(build_app_paths().logs_dir)

    def _open_config_folder(self) -> None:
        self._open_path(build_app_paths().config_dir)

    def _open_ui_guide(self) -> None:
        guide_name = "UI_GUIDE_JA.md" if self.language_var.get() == "ja" else "UI_GUIDE_EN.md"
        guide_path = build_app_paths().resources_dir / "docs" / guide_name
        if guide_path.exists():
            subprocess.run(["open", str(guide_path)], check=False)

    def _open_github(self) -> None:
        subprocess.run(["open", "https://github.com/asuka0611/physical-ai-sandbox"], check=False)

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
        if snapshot.error_message:
            state_key = "ready"
            if self._shown_error_message != snapshot.error_message:
                self._shown_error_message = snapshot.error_message
                from tkinter import messagebox

                messagebox.showerror("Viewer起動失敗", snapshot.error_message)
        elif not snapshot.running:
            state_key = "ready"
        self.status_vars["episode"].set(str(snapshot.episode))
        if snapshot.error_message and snapshot.max_steps <= 1:
            self.status_vars["step"].set("起動失敗")
        else:
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
