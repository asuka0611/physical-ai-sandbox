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
from physical_ai_sandbox.ui.input_manager import InputManager


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
        self._restart_times: list[float] = []

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

    def restart_viewer(self) -> None:
        now = time.monotonic()
        self._restart_times = [item for item in self._restart_times if now - item < 60.0]
        if len(self._restart_times) >= 3:
            self.state_store.update(
                running=False,
                paused=True,
                last_event="restart blocked",
                error_message="60秒以内にViewer再起動が3回失敗しました。ログを確認してください。",
            )
            return
        self._restart_times.append(now)
        self.stop()
        self.join(timeout=5.0)
        self.state_store.update(
            running=False,
            paused=True,
            step=0,
            error_message=None,
            last_event="viewer restarting",
            viewer_connected=False,
        )
        self.start()

    def emergency_stop(self) -> None:
        self.command_queue.put("emergency_stop")
        self.state_store.update(running=False, paused=True, last_event="emergency stop")

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
                self.state_store.update(
                    running=False,
                    paused=True,
                    last_event="viewer stopped",
                    viewer_connected=False,
                )
        except Exception as exc:
            if not self.stop_event.is_set():
                self._publish_startup_error(exc, traceback.format_exc())

    def _handle_message(self, message: dict[str, object]) -> None:
        message_type = message.get("type")
        if message_type == "snapshot":
            snapshot = ControlPanelSnapshot.from_message(message)
            if snapshot.language != self.language:
                snapshot = replace(snapshot, language=self.language)
            self.state_store.replace(replace(snapshot, viewer_connected=True))
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
                viewer_connected=False,
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
                viewer_connected=False,
            )
        else:
            self.state_store.update(
                running=False,
                paused=True,
                last_event="viewer closed",
                viewer_connected=False,
            )

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
            viewer_connected=False,
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
        self.root.title("Physical AI Sandbox Workspace")
        self.root.configure(bg="#20242a")
        self.root.minsize(1120, 720)
        self.language_var = tk.StringVar(value=self.state_store.snapshot().language)
        self.step_size_var = tk.DoubleVar(value=0.8)
        self.status_vars: dict[str, Any] = {}
        self.buttons: dict[str, Any] = {}
        self.labels: dict[str, Any] = {}
        self._shown_error_message: str | None = None
        self.input_manager = InputManager()
        self._evaluation_process: subprocess.Popen[bytes] | None = None
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
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        toolbar = tk.Frame(self.root, bg="#171b20", padx=10, pady=8)
        toolbar.grid(row=0, column=0, sticky="ew")
        self._build_toolbar(toolbar)

        workspace = tk.PanedWindow(
            self.root,
            orient="horizontal",
            sashwidth=5,
            bg="#20242a",
            bd=0,
            showhandle=False,
        )
        workspace.grid(row=1, column=0, sticky="nsew")

        left_panel = tk.Frame(workspace, bg="#20242a", padx=12, pady=10, width=260)
        center_panel = tk.Frame(workspace, bg="#111827", padx=12, pady=10, width=520)
        right_panel = tk.Frame(workspace, bg="#20242a", padx=12, pady=10, width=300)
        workspace.add(left_panel, minsize=220)
        workspace.add(center_panel, minsize=360)
        workspace.add(right_panel, minsize=260)

        bottom = tk.PanedWindow(
            self.root,
            orient="vertical",
            sashwidth=5,
            bg="#20242a",
            bd=0,
            showhandle=False,
        )
        bottom.grid(row=2, column=0, sticky="ew")
        bottom_panel = tk.Frame(bottom, bg="#171b20", padx=12, pady=8, height=150)
        bottom.add(bottom_panel, minsize=110)

        self._build_left_sidebar(left_panel)
        self._build_viewer_panel(center_panel)
        self._build_inspector(right_panel)
        self._build_bottom_panel(bottom_panel)
        self._render_text()
        self.root.focus_set()

    def _build_toolbar(self, parent: object) -> None:
        ttk = self.ttk
        toolbar_commands = [
            ("start", "start"),
            ("toggle_pause", "pause"),
            ("reset", "reset"),
            ("reset_camera", "reset_camera"),
            ("restart_viewer", "Restart Viewer"),
            ("restart_all", "Restart All"),
            ("emergency_stop", "Emergency Stop"),
            ("quit", "quit"),
        ]
        for index, (command, label_key) in enumerate(toolbar_commands):
            button = ttk.Button(
                parent,
                text=translate(label_key, self.language_var.get()),
                takefocus=False,
                command=lambda name=command: self._send(name),
            )
            button.grid(row=0, column=index, sticky="ew", padx=3)
            self.buttons[command] = button
        parent.grid_columnconfigure(len(toolbar_commands), weight=1)
        self.labels["language"] = self.tk.Label(parent, bg="#171b20", fg="#cbd5e1")
        self.labels["language"].grid(row=0, column=len(toolbar_commands), sticky="e", padx=(12, 4))
        language_menu = ttk.OptionMenu(
            parent,
            self.language_var,
            self.language_var.get(),
            "ja",
            "en",
            command=self._set_language,
        )
        language_menu.configure(takefocus=False)
        language_menu.grid(row=0, column=len(toolbar_commands) + 1, sticky="e")

    def _build_left_sidebar(self, parent: object) -> None:
        tk = self.tk
        ttk = self.ttk
        tk.Label(
            parent,
            text="Project / Scene",
            bg="#20242a",
            fg="#f4f7fb",
            font=("Helvetica", 14, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        tree = ttk.Treeview(parent, height=12, show="tree")
        tree.pack(fill="both", expand=True)
        root = tree.insert("", "end", text="Scene", open=True)
        robot = tree.insert(root, "end", text="Robot: Panda", open=True)
        for index in range(7):
            tree.insert(robot, "end", text=f"J{index + 1}  Joint {index + 1}")
        tree.insert(robot, "end", text="Gripper")
        tree.insert(root, "end", text="Table")
        tree.insert(root, "end", text="Target Object")
        tree.insert(root, "end", text="Goal Area")

        policy_frame = tk.LabelFrame(
            parent, bg="#20242a", fg="#f4f7fb", text="Policy", padx=8, pady=8
        )
        policy_frame.pack(fill="x", pady=(12, 0))
        self.policy_var = tk.StringVar(value="Manual")
        policy_menu = ttk.OptionMenu(
            policy_frame, self.policy_var, "Manual", "Manual", "Random", "BC", "PPO"
        )
        policy_menu.configure(takefocus=False)
        policy_menu.pack(fill="x")
        self.model_path_var = tk.StringVar(value="models/bc_grasp_lift_v1")
        model_entry = ttk.Entry(policy_frame, textvariable=self.model_path_var)
        model_entry.pack(fill="x", pady=(6, 0))

    def _build_viewer_panel(self, parent: object) -> None:
        tk = self.tk
        ttk = self.ttk
        tk.Label(
            parent,
            text="3D Viewport",
            bg="#111827",
            fg="#f8fafc",
            font=("Helvetica", 16, "bold"),
        ).pack(anchor="w")
        tk.Label(
            parent,
            text=(
                "MuJoCo Viewerは安定性のため別プロセスで表示します。"
                "位置リセットと前面表示で統合ワークスペースとして扱います。"
            ),
            wraplength=500,
            justify="left",
            bg="#111827",
            fg="#94a3b8",
        ).pack(anchor="w", pady=(4, 10))
        status_frame = tk.LabelFrame(
            parent, bg="#111827", fg="#f4f7fb", text="Status", padx=10, pady=8
        )
        status_frame.pack(fill="x")
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
                "viewer",
                "selected_joint",
                "input_context",
            ],
        ):
            label = tk.Label(status_frame, text=key, bg="#111827", fg="#94a3b8")
            label.grid(row=index // 3, column=(index % 3) * 2, sticky="w", padx=(0, 6), pady=2)
            value = tk.StringVar(value="-")
            value_label = tk.Label(status_frame, textvariable=value, bg="#111827", fg="#f8fafc")
            value_label.grid(row=index // 3, column=(index % 3) * 2 + 1, sticky="w", padx=(0, 16))
            self.labels[key] = label
            self.status_vars[key] = value
        action_frame = tk.Frame(parent, bg="#111827")
        action_frame.pack(fill="x", pady=(12, 0))
        for index, command in enumerate(["reset_camera", "front_viewer", "viewer_layout"]):
            text = {"front_viewer": "Viewerを前面へ", "viewer_layout": "Viewer位置リセット"}.get(
                command,
                translate(command, self.language_var.get()),
            )
            button = ttk.Button(
                action_frame,
                text=text,
                takefocus=False,
                command=lambda name=command: self._send(name),
            )
            button.grid(row=0, column=index, padx=3, sticky="ew")
            self.buttons[command] = button

    def _build_inspector(self, parent: object) -> None:
        tk = self.tk
        ttk = self.ttk
        tk.Label(
            parent,
            text="Robot Inspector",
            bg="#20242a",
            fg="#f4f7fb",
            font=("Helvetica", 14, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        joints_frame = tk.LabelFrame(parent, bg="#20242a", fg="#f4f7fb", padx=10, pady=8)
        joints_frame.pack(fill="both", expand=True)
        self.labels["joints"] = joints_frame
        joint_names = [
            "Base Rotation",
            "Shoulder",
            "Upper Arm",
            "Elbow",
            "Wrist 1",
            "Wrist 2",
            "Wrist 3",
        ]
        for index, joint_name in enumerate(joint_names):
            row = tk.Frame(joints_frame, bg="#20242a")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"J{index + 1}", width=3, bg="#20242a", fg="#38bdf8").pack(
                side="left"
            )
            tk.Label(row, text=joint_name, width=14, anchor="w", bg="#20242a", fg="#cbd5e1").pack(
                side="left"
            )
            ttk.Button(
                row,
                text="-",
                width=3,
                takefocus=False,
                command=lambda joint=index: self._send("joint_negative", joint),
            ).pack(side="left", padx=2)
            ttk.Button(
                row,
                text="+",
                width=3,
                takefocus=False,
                command=lambda joint=index: self._send("joint_positive", joint),
            ).pack(side="left", padx=2)
            ttk.Button(
                row,
                text="Focus",
                width=6,
                takefocus=False,
                command=lambda joint=index: self._send("select_joint", joint),
            ).pack(side="left", padx=2)

        self.labels["step_size"] = tk.Label(parent, bg="#20242a", fg="#cbd5e1")
        self.labels["step_size"].pack(anchor="w", pady=(10, 0))
        scale = ttk.Scale(
            parent,
            variable=self.step_size_var,
            from_=0.1,
            to=1.0,
            command=lambda value: self._send("set_step_size", float(value)),
        )
        scale.pack(fill="x", pady=(4, 0))

    def _build_bottom_panel(self, parent: object) -> None:
        tk = self.tk
        notebook = self.ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)
        console = tk.Frame(notebook, bg="#171b20", padx=8, pady=8)
        metrics = tk.Frame(notebook, bg="#171b20", padx=8, pady=8)
        evaluation = tk.Frame(notebook, bg="#171b20", padx=8, pady=8)
        timeline = tk.Frame(notebook, bg="#171b20", padx=8, pady=8)
        notebook.add(console, text="Console")
        notebook.add(metrics, text="Metrics")
        notebook.add(evaluation, text="Evaluation")
        notebook.add(timeline, text="Timeline")

        self.help_text = tk.StringVar(value="")
        tk.Label(
            console, textvariable=self.help_text, justify="left", bg="#171b20", fg="#dbeafe"
        ).pack(anchor="w")
        tk.Label(
            metrics,
            text="Reward / Success / Object height are updated from the simulation snapshot.",
            bg="#171b20",
            fg="#cbd5e1",
        ).pack(anchor="w")

        self.eval_episode_var = tk.StringVar(value="3")
        self.eval_seed_var = tk.StringVar(value="42")
        self.eval_status_var = tk.StringVar(value="評価待機中")
        for label, var in [("Episodes", self.eval_episode_var), ("Seed", self.eval_seed_var)]:
            row = tk.Frame(evaluation, bg="#171b20")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, width=10, anchor="w", bg="#171b20", fg="#94a3b8").pack(
                side="left"
            )
            self.ttk.Entry(row, textvariable=var, width=10).pack(side="left")
        self.ttk.Button(
            evaluation, text="評価開始", takefocus=False, command=self._start_evaluation
        ).pack(side="left", padx=3, pady=6)
        self.ttk.Button(
            evaluation, text="評価停止", takefocus=False, command=self._stop_evaluation
        ).pack(side="left", padx=3, pady=6)
        tk.Label(evaluation, textvariable=self.eval_status_var, bg="#171b20", fg="#f8fafc").pack(
            anchor="w", pady=(36, 0)
        )

        tk.Label(
            timeline,
            text=(
                "Trajectory replay MVP: JSON action trajectory is saved by "
                "evaluate_policy.py. Viewer playback controls are pending."
            ),
            wraplength=760,
            justify="left",
            bg="#171b20",
            fg="#cbd5e1",
        ).pack(anchor="w")

    def _bind_keys(self) -> None:
        self.root.bind("<FocusIn>", self._on_focus_in)
        self.root.bind("<FocusOut>", self._on_focus_out)
        self.root.bind("<KeyPress>", self._on_key_press)
        self.root.bind("<KeyRelease>", self._on_key_release)

    def _on_focus_in(self, event: object) -> None:
        widget = getattr(event, "widget", self.root)
        self.input_manager.focus_in(widget)

    def _on_focus_out(self, _event: object) -> None:
        self.input_manager.focus_out()

    def _on_key_press(self, event: object) -> str | None:
        command = self.input_manager.handle_key_press(event)  # type: ignore[arg-type]
        if command is None:
            return None
        if command == "clear_focus":
            self.root.focus_set()
            return "break"
        self._send(command)
        return "break"

    def _on_key_release(self, event: object) -> None:
        self.input_manager.handle_key_release(event)  # type: ignore[arg-type]

    def _send(self, name: str, value: str | float | int | None = None) -> None:
        if name == "quit":
            self.close()
            return
        if name == "restart_viewer":
            Thread(target=self.runtime.restart_viewer, daemon=True).start()
            return
        if name == "restart_all":
            Thread(target=self.runtime.restart_viewer, daemon=True).start()
            return
        if name == "emergency_stop":
            self.runtime.emergency_stop()
            return
        if name == "front_viewer":
            self._front_viewer()
            return
        if name == "viewer_layout":
            self._reset_viewer_layout()
            return
        self.command_queue.put(name, value)
        self.root.focus_set()

    def _start_evaluation(self) -> None:
        if self._evaluation_process is not None and self._evaluation_process.poll() is None:
            self.eval_status_var.set("評価は既に実行中です")
            return
        policy = self.policy_var.get().strip().lower()
        if policy == "manual":
            self.eval_status_var.set("Manualは自動評価対象外です")
            return
        output_dir = build_app_paths().logs_dir / "policy_evaluation_ui"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{policy}_{int(time.time())}.json"
        command = [
            sys.executable,
            "scripts/evaluate_policy.py",
            "--policy",
            "bc" if policy == "bc" else policy,
            "--episodes",
            self.eval_episode_var.get(),
            "--seed",
            self.eval_seed_var.get(),
            "--max-steps",
            "200",
            "--headless",
            "--output",
            str(output_path),
        ]
        if policy in {"bc", "ppo"}:
            command.extend(["--model", self.model_path_var.get()])
        log_path = output_path.with_suffix(".log")
        log_handle = log_path.open("ab")
        self._evaluation_process = subprocess.Popen(
            command,
            cwd=str(Path.cwd()),
            stdout=log_handle,
            stderr=log_handle,
        )
        log_handle.close()
        self.eval_status_var.set(f"評価中: {policy} -> {output_path}")

    def _stop_evaluation(self) -> None:
        process = self._evaluation_process
        if process is None or process.poll() is not None:
            self.eval_status_var.set("停止対象の評価はありません")
            return
        process.terminate()
        try:
            process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            process.kill()
        self.eval_status_var.set("評価を停止しました。完了済み出力を確認してください。")

    def _front_viewer(self) -> None:
        if sys.platform != "darwin":
            self.status_vars.get("last_event", self.tk.StringVar()).set(
                "Viewer front is macOS only"
            )
            return
        subprocess.run(
            [
                "osascript",
                "-e",
                (
                    'tell application "System Events" to if exists process "mjpython" '
                    'then set frontmost of process "mjpython" to true'
                ),
            ],
            check=False,
        )

    def _reset_viewer_layout(self) -> None:
        if sys.platform != "darwin":
            self.status_vars.get("last_event", self.tk.StringVar()).set(
                "Viewer layout is macOS only"
            )
            return
        script = "\n".join(
            [
                'tell application "System Events"',
                (
                    '  if exists process "python3" then set position of window 1 '
                    'of process "python3" to {60, 80}'
                ),
                (
                    '  if exists process "python3" then set size of window 1 '
                    'of process "python3" to {620, 820}'
                ),
                (
                    '  if exists process "mjpython" then set position of window 1 '
                    'of process "mjpython" to {700, 80}'
                ),
                (
                    '  if exists process "mjpython" then set size of window 1 '
                    'of process "mjpython" to {1040, 820}'
                ),
                "end tell",
            ],
        )
        subprocess.run(["osascript", "-e", script], check=False)

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
            if command in self.buttons:
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
        if "viewer" in self.status_vars:
            self.status_vars["viewer"].set(
                "Connected" if snapshot.viewer_connected else "Disconnected"
            )
        if "selected_joint" in self.status_vars:
            self.status_vars["selected_joint"].set(
                "-" if snapshot.selected_joint is None else f"J{snapshot.selected_joint + 1}",
            )
        if "input_context" in self.status_vars:
            self.status_vars["input_context"].set(self.input_manager.context.value)
        self.status_vars["last_event"].set(
            f"{translate(state_key, language)} / {snapshot.last_event}",
        )
        if "toggle_pause" in self.buttons:
            self.buttons["toggle_pause"].configure(
                text=translate("resume" if snapshot.paused else "pause", language),
            )
        if "toggle_recording" in self.buttons:
            self.buttons["toggle_recording"].configure(
                text=translate(
                    "stop_recording" if snapshot.recording else "start_recording",
                    language,
                ),
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
                    "Esc: 入力解除",
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
                "Esc: clear focus",
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
