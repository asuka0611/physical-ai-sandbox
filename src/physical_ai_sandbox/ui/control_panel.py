from __future__ import annotations

import base64
import contextlib
import json
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

    def put(self, name: str, value: object | None = None) -> None:
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
        self._frame_lock = Lock()
        self._latest_frame: bytes | None = None
        self._latest_frame_sequence = 0
        self._latest_frame_metadata: dict[str, object] = {}

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

    def latest_frame(self) -> tuple[int, bytes | None]:
        with self._frame_lock:
            return self._latest_frame_sequence, self._latest_frame

    def latest_frame_metadata(self) -> dict[str, object]:
        with self._frame_lock:
            return dict(self._latest_frame_metadata)

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
            self.state_store.replace(snapshot)
            return
        if message_type == "frame":
            payload = message.get("ppm")
            if isinstance(payload, str):
                with self._frame_lock:
                    self._latest_frame = base64.b64decode(payload.encode("ascii"))
                    self._latest_frame_sequence = int(message.get("sequence", 0))
                    metadata = message.get("metadata")
                    self._latest_frame_metadata = metadata if isinstance(metadata, dict) else {}
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
        self.workspace_state_path = build_app_paths().app_support_dir / "workspace_state.json"
        self.workspace_state = self._load_workspace_state()
        self.language_var = tk.StringVar(value=self.state_store.snapshot().language)
        self.step_size_var = tk.DoubleVar(value=0.8)
        self.mode_var = tk.StringVar(value=str(self.workspace_state.get("mode", "Manual Test")))
        self.overlay_enabled_var = tk.BooleanVar(
            value=bool(self.workspace_state.get("overlay_enabled", True)),
        )
        self.status_vars: dict[str, Any] = {}
        self.buttons: dict[str, Any] = {}
        self.labels: dict[str, Any] = {}
        self.joint_rows: dict[int, Any] = {}
        self._shown_error_message: str | None = None
        self._viewport_image: Any | None = None
        self._viewport_frame_sequence = -1
        self._viewport_image_origin = (0, 0)
        self._viewport_drag: dict[str, object] | None = None
        self._viewport_pointer = (0, 0)
        self._camera_state_sent = False
        self._mode_state_sent = False
        self._save_pending = False
        self._last_viewport_size = (0, 0)
        self._maximized = False
        self._panel_visible = {"left": True, "right": True, "bottom": True}
        self.viewport_canvas: Any | None = None
        self.viewport_status_var = tk.StringVar(value="Viewport initializing...")
        self.workspace_paned: Any | None = None
        self.vertical_paned: Any | None = None
        self.left_panel: Any | None = None
        self.center_panel: Any | None = None
        self.right_panel: Any | None = None
        self.bottom_panel: Any | None = None
        self.bottom_notebook: Any | None = None
        self.input_manager = InputManager()
        self._evaluation_process: subprocess.Popen[bytes] | None = None
        self._build()
        self.command_queue.put("set_mode", self.mode_var.get())
        self._bind_keys()
        self._refresh()
        self._build_menu()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(200, self._show_workspace_window)

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
        self._save_workspace_state()
        self.runtime.stop()
        self.root.after(100, self.root.destroy)

    def _show_workspace_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _build(self) -> None:
        tk = self.tk
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        toolbar = tk.Frame(self.root, bg="#171b20", padx=10, pady=8)
        toolbar.grid(row=0, column=0, sticky="ew")
        self._build_toolbar(toolbar)

        vertical = tk.PanedWindow(
            self.root,
            orient="vertical",
            sashwidth=6,
            bg="#111827",
            bd=0,
            showhandle=False,
        )
        vertical.grid(row=1, column=0, sticky="nsew")
        self.vertical_paned = vertical

        workspace = tk.PanedWindow(
            self.root,
            orient="horizontal",
            sashwidth=5,
            bg="#20242a",
            bd=0,
            showhandle=False,
        )
        self.workspace_paned = workspace

        left_panel = tk.Frame(workspace, bg="#20242a", padx=12, pady=10, width=260)
        center_panel = tk.Frame(workspace, bg="#111827", padx=12, pady=10, width=520)
        right_panel = tk.Frame(workspace, bg="#20242a", padx=12, pady=10, width=300)
        self.left_panel = left_panel
        self.center_panel = center_panel
        self.right_panel = right_panel
        workspace.add(left_panel, minsize=220)
        workspace.add(center_panel, minsize=360)
        workspace.add(right_panel, minsize=260)

        bottom_panel = tk.Frame(vertical, bg="#171b20", padx=12, pady=8, height=170)
        self.bottom_panel = bottom_panel
        vertical.add(workspace, minsize=420)
        vertical.add(bottom_panel, minsize=90)

        self._build_left_sidebar(left_panel)
        self._build_viewer_panel(center_panel)
        self._build_inspector(right_panel)
        self._build_bottom_panel(bottom_panel)
        self._render_text()
        self.root.after(150, self._restore_layout)
        self.root.focus_set()

    def _build_toolbar(self, parent: object) -> None:
        ttk = self.ttk
        toolbar_commands = [
            ("start", "start"),
            ("toggle_pause", "pause"),
            ("reset", "reset"),
            ("reset_camera", "reset_camera"),
            ("restart_viewer", "restart_viewport"),
            ("restart_all", "restart_all"),
            ("toggle_viewport_max", "viewport_max"),
            ("zen_mode", "zen_mode"),
            ("layout_reset", "layout_reset"),
            ("emergency_stop", "emergency_stop"),
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
        self.labels["mode"] = self.tk.Label(parent, bg="#171b20", fg="#cbd5e1")
        self.labels["mode"].grid(row=0, column=len(toolbar_commands) + 2, sticky="e", padx=(10, 4))
        mode_menu = ttk.OptionMenu(
            parent,
            self.mode_var,
            self.mode_var.get(),
            "Manual Test",
            "AI Recording",
            command=lambda _value: self._on_mode_changed(),
        )
        mode_menu.configure(takefocus=False)
        mode_menu.grid(row=0, column=len(toolbar_commands) + 3, sticky="e")
        rec_button = ttk.Button(
            parent,
            text="REC",
            takefocus=False,
            command=lambda: self._send("start_recording"),
        )
        rec_button.grid(row=0, column=len(toolbar_commands) + 4, sticky="e", padx=3)
        self.buttons["start_recording"] = rec_button
        stop_rec_button = ttk.Button(
            parent,
            text="Stop REC",
            takefocus=False,
            command=lambda: self._send("stop_recording"),
        )
        stop_rec_button.grid(row=0, column=len(toolbar_commands) + 5, sticky="e", padx=3)
        self.buttons["stop_recording"] = stop_rec_button

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
        self.scene_tree = tree
        root = tree.insert("", "end", text="Scene", open=True)
        robot = tree.insert(root, "end", text="Robot: Panda", open=True)
        for index in range(7):
            tree.insert(robot, "end", iid=f"joint_{index}", text=f"J{index + 1}  Joint {index + 1}")
        tree.insert(robot, "end", text="Gripper")
        tree.insert(root, "end", text="Table")
        tree.insert(root, "end", text="Target Object")
        tree.insert(root, "end", text="Goal Area")
        tree.bind("<<TreeviewSelect>>", self._on_scene_tree_select)

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
        viewport_shell = tk.Frame(
            parent,
            bg="#030712",
            highlightthickness=1,
            highlightbackground="#334155",
        )
        viewport_shell.pack(fill="both", expand=True, pady=(8, 10))
        viewport_shell.grid_columnconfigure(0, weight=1)
        viewport_shell.grid_rowconfigure(0, weight=1)
        self.viewport_canvas = tk.Canvas(
            viewport_shell,
            bg="#020617",
            highlightthickness=0,
            takefocus=True,
        )
        self.viewport_canvas.grid(row=0, column=0, sticky="nsew")
        self.viewport_canvas.bind("<Button-1>", self._on_viewport_press)
        self.viewport_canvas.bind("<B1-Motion>", self._on_viewport_drag)
        self.viewport_canvas.bind("<ButtonRelease-1>", self._on_viewport_release)
        self.viewport_canvas.bind("<Button-2>", self._on_viewport_press)
        self.viewport_canvas.bind("<B2-Motion>", self._on_viewport_drag)
        self.viewport_canvas.bind("<ButtonRelease-2>", self._on_viewport_release)
        self.viewport_canvas.bind("<MouseWheel>", self._on_viewport_wheel)
        self.viewport_canvas.bind("<Button-4>", self._on_viewport_wheel)
        self.viewport_canvas.bind("<Button-5>", self._on_viewport_wheel)
        self.viewport_canvas.bind("<Double-Button-1>", self._on_viewport_double_click)
        self.viewport_canvas.bind("<Configure>", self._on_viewport_resize)
        self.viewport_canvas.create_text(
            20,
            20,
            anchor="nw",
            text="Viewport initializing...",
            fill="#e2e8f0",
            font=("Helvetica", 13, "bold"),
            tags=("viewport_status",),
        )
        tk.Label(
            viewport_shell,
            textvariable=self.viewport_status_var,
            bg="#030712",
            fg="#94a3b8",
            padx=8,
            pady=4,
        ).grid(row=1, column=0, sticky="ew")
        camera_frame = tk.Frame(parent, bg="#111827")
        camera_frame.pack(fill="x", pady=(0, 8))
        for index, preset in enumerate(
            ["front", "right", "top", "back", "left", "bottom", "isometric"],
        ):
            ttk.Button(
                camera_frame,
                text=preset.title(),
                takefocus=False,
                command=lambda name=preset: self._send("camera_preset", {"name": name}),
            ).grid(row=0, column=index, padx=2, sticky="ew")
            camera_frame.grid_columnconfigure(index, weight=1)
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
            text = {"front_viewer": "Viewportへフォーカス", "viewer_layout": "Viewport更新"}.get(
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
            self.joint_rows[index] = row
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
        self.bottom_notebook = notebook
        notebook.pack(fill="both", expand=True)
        console = tk.Frame(notebook, bg="#171b20", padx=8, pady=8)
        metrics = tk.Frame(notebook, bg="#171b20", padx=8, pady=8)
        evaluation = tk.Frame(notebook, bg="#171b20", padx=8, pady=8)
        timeline = tk.Frame(notebook, bg="#171b20", padx=8, pady=8)
        problems = tk.Frame(notebook, bg="#171b20", padx=8, pady=8)
        notebook.add(console, text="Console")
        notebook.add(metrics, text="Metrics")
        notebook.add(evaluation, text="Evaluation")
        notebook.add(timeline, text="Timeline")
        notebook.add(problems, text="Problems")
        notebook.bind("<<NotebookTabChanged>>", lambda _event: self._schedule_workspace_save())

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
        self.ttk.Checkbutton(
            metrics,
            text="Viewport overlay",
            variable=self.overlay_enabled_var,
            command=self._schedule_workspace_save,
        ).pack(anchor="w", pady=(8, 0))

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
        tk.Label(
            problems,
            text=(
                "Replay timeline controls and long-run memory verification are still pending. "
                "Camera, layout, mode, overlay, and joint-selection state are persisted."
            ),
            wraplength=760,
            justify="left",
            bg="#171b20",
            fg="#fbbf24",
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

    def _on_scene_tree_select(self, _event: object) -> None:
        tree = getattr(self, "scene_tree", None)
        if tree is None:
            return
        selected = tree.selection()
        if not selected:
            return
        item = str(selected[0])
        if item.startswith("joint_"):
            self._select_joint(int(item.removeprefix("joint_")))

    def _select_joint(self, joint: int) -> None:
        self.workspace_state["selected_joint"] = joint
        self._highlight_joint_row(joint)
        tree = getattr(self, "scene_tree", None)
        if tree is not None:
            with contextlib.suppress(Exception):
                tree.selection_set(f"joint_{joint}")
        self._send("select_joint", joint)

    def _on_mode_changed(self) -> None:
        self.workspace_state["mode"] = self.mode_var.get()
        self.command_queue.put("set_mode", self.mode_var.get())
        self._mode_state_sent = True
        self._schedule_workspace_save()

    def _on_viewport_press(self, event: object) -> str:
        self.root.focus_set()
        x = int(getattr(event, "x", 0))
        y = int(getattr(event, "y", 0))
        gizmo_preset = self._camera_gizmo_hit(x, y)
        if gizmo_preset is not None:
            self._send("camera_preset", {"name": gizmo_preset})
            self._viewport_drag = None
            return "break"
        clicked = self._joint_at_canvas_point(x, y)
        if clicked is not None:
            self._select_joint(clicked)
            self._viewport_drag = None
            return "break"
        state = int(getattr(event, "state", 0))
        button = int(getattr(event, "num", 1))
        mode = "pan" if button == 2 or state & 0x1 else "orbit"
        self._viewport_drag = {"x": x, "y": y, "mode": mode}
        return "break"

    def _on_viewport_drag(self, event: object) -> str:
        if self._viewport_drag is None:
            return "break"
        x = int(getattr(event, "x", 0))
        y = int(getattr(event, "y", 0))
        previous_x = int(self._viewport_drag["x"])
        previous_y = int(self._viewport_drag["y"])
        dx = x - previous_x
        dy = y - previous_y
        self._viewport_drag["x"] = x
        self._viewport_drag["y"] = y
        mode = str(self._viewport_drag["mode"])
        command = "camera_pan" if mode == "pan" else "camera_orbit"
        self._send(command, {"dx": dx, "dy": dy})
        return "break"

    def _on_viewport_release(self, _event: object) -> str:
        self._viewport_drag = None
        return "break"

    def _on_viewport_wheel(self, event: object) -> str:
        delta = getattr(event, "delta", 0)
        if not delta:
            delta = 1 if int(getattr(event, "num", 0)) == 4 else -1
        self._send("camera_zoom", {"delta": 1 if int(delta) > 0 else -1})
        return "break"

    def _on_viewport_double_click(self, event: object) -> str:
        joint = self._joint_at_canvas_point(
            int(getattr(event, "x", 0)),
            int(getattr(event, "y", 0)),
        )
        if joint is not None:
            self._select_joint(joint)
        else:
            self._send("camera_preset", {"name": "isometric"})
        return "break"

    def _on_viewport_resize(self, event: object) -> None:
        width = max(240, int(getattr(event, "width", 0)))
        height = max(180, int(getattr(event, "height", 0)) - 24)
        previous_width, previous_height = self._last_viewport_size
        if abs(width - previous_width) < 24 and abs(height - previous_height) < 24:
            return
        self._last_viewport_size = (width, height)
        self._send("camera_viewport_size", {"width": width, "height": height})

    def _send(self, name: str, value: object | None = None) -> None:
        if name == "quit":
            self.close()
            return
        if name == "restart_viewer":
            self._camera_state_sent = False
            self._mode_state_sent = False
            Thread(target=self.runtime.restart_viewer, daemon=True).start()
            return
        if name == "restart_all":
            self._camera_state_sent = False
            self._mode_state_sent = False
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
        if name == "layout_reset":
            self._reset_layout()
            return
        if name == "toggle_viewport_max":
            self._toggle_viewport_maximized()
            return
        if name == "zen_mode":
            self._set_zen_mode()
            return
        if name == "start_recording" and self.mode_var.get() != "AI Recording":
            self.status_vars.get("last_event", self.tk.StringVar()).set(
                "Manual Testでは保存しません。AI Recordingに切り替えてください。",
            )
            return
        self.command_queue.put(name, value)
        self.root.focus_set()

    def _joint_at_canvas_point(self, x: int, y: int) -> int | None:
        metadata = self.runtime.latest_frame_metadata()
        labels = metadata.get("joint_labels")
        if not isinstance(labels, list):
            return None
        origin_x, origin_y = self._viewport_image_origin
        for label in labels:
            if not isinstance(label, dict):
                continue
            label_x = origin_x + float(label.get("x", -9999))
            label_y = origin_y + float(label.get("y", -9999))
            if abs(label_x - x) <= 18 and abs(label_y - y) <= 18:
                return int(label.get("joint", -1))
        return None

    def _camera_gizmo_hit(self, x: int, y: int) -> str | None:
        canvas = self.viewport_canvas
        if canvas is None:
            return None
        width = max(1, int(canvas.winfo_width()))
        center_x = width - 70
        center_y = 42
        if abs(x - center_x) <= 16 and abs(y - center_y) <= 16:
            return "isometric"
        if abs(x - center_x) <= 18 and abs(y - (center_y - 38)) <= 20:
            return "top"
        if abs(x - (center_x - 46)) <= 20 and abs(y - center_y) <= 18:
            return "front"
        if abs(x - (center_x + 46)) <= 20 and abs(y - center_y) <= 18:
            return "right"
        return None

    def _highlight_joint_row(self, selected_joint: int | None) -> None:
        for index, row in self.joint_rows.items():
            row.configure(bg="#3b2f12" if index == selected_joint else "#20242a")

    def _load_workspace_state(self) -> dict[str, object]:
        try:
            return json.loads(self.workspace_state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_workspace_state(self) -> None:
        self._save_pending = False
        metadata = self.runtime.latest_frame_metadata()
        camera = metadata.get("camera")
        if isinstance(camera, dict):
            self.workspace_state["camera"] = camera
        self.workspace_state["mode"] = self.mode_var.get()
        self.workspace_state["overlay_enabled"] = bool(self.overlay_enabled_var.get())
        if self.bottom_notebook is not None:
            with contextlib.suppress(Exception):
                self.workspace_state["active_tab"] = self.bottom_notebook.index("current")
        self.workspace_state["panel_visible"] = dict(self._panel_visible)
        if self.workspace_paned is not None:
            self.workspace_state["workspace_sashes"] = self._sash_positions(self.workspace_paned)
        if self.vertical_paned is not None:
            self.workspace_state["vertical_sashes"] = self._sash_positions(self.vertical_paned)
        self.workspace_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.workspace_state_path.write_text(
            json.dumps(self.workspace_state, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _schedule_workspace_save(self) -> None:
        if self._save_pending:
            return
        self._save_pending = True
        self.root.after(250, self._save_workspace_state)

    def _restore_layout(self) -> None:
        panel_visible = self.workspace_state.get("panel_visible")
        if isinstance(panel_visible, dict):
            self._panel_visible.update(
                {key: bool(panel_visible.get(key, True)) for key in self._panel_visible},
            )
            self._apply_panel_visibility()
        selected = self.workspace_state.get("selected_joint")
        if isinstance(selected, int) and 0 <= selected < 7:
            self._highlight_joint_row(selected)
            self.command_queue.put("select_joint", selected)
        active_tab = self.workspace_state.get("active_tab")
        if self.bottom_notebook is not None and isinstance(active_tab, int):
            with contextlib.suppress(Exception):
                self.bottom_notebook.select(active_tab)
        self._restore_sashes()

    def _reset_layout(self) -> None:
        self._maximized = False
        self._panel_visible = {"left": True, "right": True, "bottom": True}
        self._apply_panel_visibility()
        self.workspace_state.clear()
        self._save_workspace_state()

    def _toggle_viewport_maximized(self) -> None:
        self._maximized = not self._maximized
        visible = not self._maximized
        self._panel_visible = {"left": visible, "right": visible, "bottom": visible}
        self._apply_panel_visibility()
        self._schedule_workspace_save()

    def _set_zen_mode(self) -> None:
        self._maximized = True
        self._panel_visible = {"left": False, "right": False, "bottom": False}
        self._apply_panel_visibility()
        self._schedule_workspace_save()

    def _apply_panel_visibility(self) -> None:
        if self.workspace_paned is not None and self.center_panel is not None:
            with contextlib.suppress(Exception):
                for pane in list(self.workspace_paned.panes()):
                    self.workspace_paned.forget(pane)
            if self._panel_visible["left"] and self.left_panel is not None:
                self.workspace_paned.add(self.left_panel, minsize=180)
            self.workspace_paned.add(self.center_panel, minsize=360)
            if self._panel_visible["right"] and self.right_panel is not None:
                self.workspace_paned.add(self.right_panel, minsize=220)
        if self.vertical_paned is not None and self.bottom_panel is not None:
            panes = list(self.vertical_paned.panes())
            bottom_path = str(self.bottom_panel)
            has_bottom = bottom_path in panes
            if self._panel_visible["bottom"] and not has_bottom:
                self.vertical_paned.add(self.bottom_panel, minsize=90)
            if not self._panel_visible["bottom"] and has_bottom:
                self.vertical_paned.forget(self.bottom_panel)

    def _restore_sashes(self) -> None:
        workspace_sashes = self.workspace_state.get("workspace_sashes")
        vertical_sashes = self.workspace_state.get("vertical_sashes")
        if isinstance(workspace_sashes, list) and self.workspace_paned is not None:
            self._place_sashes(self.workspace_paned, workspace_sashes)
        if isinstance(vertical_sashes, list) and self.vertical_paned is not None:
            self._place_sashes(self.vertical_paned, vertical_sashes)

    @staticmethod
    def _sash_positions(paned: object) -> list[list[int]]:
        positions: list[list[int]] = []
        for index in range(4):
            try:
                x, y = paned.sash_coord(index)  # type: ignore[attr-defined]
            except Exception:
                break
            positions.append([int(x), int(y)])
        return positions

    @staticmethod
    def _place_sashes(paned: object, positions: list[object]) -> None:
        for index, position in enumerate(positions):
            if not isinstance(position, list | tuple) or len(position) != 2:
                continue
            with contextlib.suppress(Exception):
                paned.sash_place(index, int(position[0]), int(position[1]))  # type: ignore[attr-defined]

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
        self.root.focus_set()
        if self.viewport_canvas is not None:
            self.viewport_canvas.focus_set()
        self.status_vars.get("last_event", self.tk.StringVar()).set("viewport focused")

    def _reset_viewer_layout(self) -> None:
        self._viewport_frame_sequence = -1
        self.status_vars.get("last_event", self.tk.StringVar()).set("viewport refresh requested")

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
            "restart_viewer": "restart_viewport",
            "restart_all": "restart_all",
            "emergency_stop": "emergency_stop",
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
        elif snapshot.mode == "Manual Test":
            self.status_vars["step"].set(f"Session Step {snapshot.session_step}")
        else:
            self.status_vars["step"].set(f"{snapshot.step} / {snapshot.max_steps}")
        self.status_vars["reward"].set(f"{snapshot.reward:.3f}")
        self.status_vars["grasped"].set(self._bool_text(snapshot.grasped, language))
        self.status_vars["lifted"].set(self._bool_text(snapshot.lifted, language))
        self.status_vars["success"].set(self._bool_text(snapshot.success, language))
        self.status_vars["recording"].set(self._bool_text(snapshot.recording, language))
        self.status_vars["controller"].set(snapshot.mode)
        if "viewer" in self.status_vars:
            self.status_vars["viewer"].set(
                "Connected" if snapshot.viewer_connected else "Disconnected"
            )
        if "selected_joint" in self.status_vars:
            self.status_vars["selected_joint"].set(
                "-" if snapshot.selected_joint is None else f"J{snapshot.selected_joint + 1}",
            )
            self._highlight_joint_row(snapshot.selected_joint)
        if "input_context" in self.status_vars:
            self.status_vars["input_context"].set(self.input_manager.context.value)
        self.status_vars["last_event"].set(
            f"{translate(state_key, language)} / {snapshot.last_event}",
        )
        if snapshot.viewer_connected and not self._camera_state_sent:
            camera = self.workspace_state.get("camera")
            if isinstance(camera, dict):
                self.command_queue.put("camera_state", camera)
            self._camera_state_sent = True
        if snapshot.viewer_connected and not self._mode_state_sent:
            self.command_queue.put("set_mode", self.mode_var.get())
            self._mode_state_sent = True
        self._refresh_viewport(snapshot)
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
        high_rate_refresh = (snapshot.running and not snapshot.paused) or self._viewport_drag
        refresh_ms = 33 if high_rate_refresh else 100
        self.root.after(refresh_ms, self._refresh)

    def _refresh_viewport(self, snapshot: ControlPanelSnapshot) -> None:
        canvas = self.viewport_canvas
        if canvas is None:
            return
        sequence, frame = self.runtime.latest_frame()
        if frame is not None and sequence != self._viewport_frame_sequence:
            try:
                self._viewport_image = self.tk.PhotoImage(data=frame, format="PPM")
                width = max(1, int(canvas.winfo_width()))
                height = max(1, int(canvas.winfo_height()))
                image_width = int(self._viewport_image.width())
                image_height = int(self._viewport_image.height())
                x = max(0, (width - image_width) // 2)
                y = max(0, (height - image_height) // 2)
                self._viewport_image_origin = (x, y)
                canvas.delete("viewport_frame")
                canvas.create_image(
                    x,
                    y,
                    anchor="nw",
                    image=self._viewport_image,
                    tags=("viewport_frame",),
                )
                canvas.tag_lower("viewport_frame")
                self._viewport_frame_sequence = sequence
            except Exception as exc:
                self.viewport_status_var.set(f"Viewport render error: {exc}")
        if snapshot.error_message:
            status = "起動失敗"
        elif snapshot.viewer_connected:
            status = "Embedded MuJoCo Viewport connected"
        else:
            status = "Viewport disconnected"
        self.viewport_status_var.set(status)
        canvas.delete("viewport_overlay")
        canvas.delete("joint_label")
        canvas.delete("camera_gizmo")
        metadata = self.runtime.latest_frame_metadata()
        fps = float(metadata.get("fps", 0.0) or 0.0)
        simulation_hz = float(metadata.get("simulation_hz", 0.0) or 0.0)
        if snapshot.mode == "Manual Test":
            overlay_lines = [
                "Mode: Manual Test",
                "Recording: OFF",
                f"Session Step: {snapshot.session_step}",
                f"Elapsed: {self._format_elapsed(snapshot.elapsed_seconds)}",
                f"Reward {snapshot.reward:.3f}",
                f"FPS {fps:.1f}  Simulation {simulation_hz:.1f} Hz",
                f"Policy {self.policy_var.get()}",
                (
                    "Selected -"
                    if snapshot.selected_joint is None
                    else f"Selected J{snapshot.selected_joint + 1}"
                ),
                f"Input {self.input_manager.context.value}",
            ]
        else:
            overlay_lines = [
                f"Mode: {snapshot.mode}",
                f"Recording: {'REC' if snapshot.recording else 'OFF'}",
                f"Episode {snapshot.episode}  Step {snapshot.step}/{snapshot.max_steps}",
                f"Session Step: {snapshot.session_step}",
                f"Elapsed: {self._format_elapsed(snapshot.elapsed_seconds)}",
                f"Reward {snapshot.reward:.3f}",
                f"FPS {fps:.1f}  Simulation {simulation_hz:.1f} Hz",
                f"Policy {self.policy_var.get()}",
                (
                    "Selected -"
                    if snapshot.selected_joint is None
                    else f"Selected J{snapshot.selected_joint + 1}"
                ),
                f"Input {self.input_manager.context.value}",
            ]
        if self.overlay_enabled_var.get():
            canvas.create_text(
                12,
                12,
                anchor="nw",
                text="\n".join(overlay_lines),
                fill="#f8fafc",
                font=("Helvetica", 12, "bold"),
                tags=("viewport_overlay",),
            )
        if snapshot.recording:
            canvas.create_oval(
                12,
                12,
                28,
                28,
                fill="#ef4444",
                outline="",
                tags=("viewport_overlay",),
            )
            canvas.create_text(
                36,
                20,
                anchor="w",
                text="REC",
                fill="#fecaca",
                font=("Helvetica", 12, "bold"),
                tags=("viewport_overlay",),
            )
        self._draw_joint_labels(canvas, metadata)
        self._draw_camera_gizmo(canvas)

    def _draw_joint_labels(self, canvas: object, metadata: dict[str, object]) -> None:
        labels = metadata.get("joint_labels")
        if not isinstance(labels, list):
            return
        origin_x, origin_y = self._viewport_image_origin
        for label in labels:
            if not isinstance(label, dict):
                continue
            x = origin_x + float(label.get("x", 0.0))
            y = origin_y + float(label.get("y", 0.0))
            name = str(label.get("name", "J?"))
            selected = bool(label.get("selected", False))
            fill = "#fde047" if selected else "#38bdf8"
            outline = "#f59e0b" if selected else "#0f172a"
            canvas.create_oval(
                x - 13,
                y - 13,
                x + 13,
                y + 13,
                fill=outline,
                outline="#f8fafc" if selected else "",
                width=2,
                tags=("joint_label",),
            )
            canvas.create_text(
                x,
                y,
                text=name,
                fill=fill,
                font=("Helvetica", 10, "bold"),
                tags=("joint_label",),
            )
            if selected:
                canvas.create_line(
                    x - 24,
                    y,
                    x + 24,
                    y,
                    fill="#fde047",
                    width=2,
                    tags=("joint_label",),
                )
                canvas.create_line(
                    x,
                    y - 24,
                    x,
                    y + 24,
                    fill="#fde047",
                    width=2,
                    tags=("joint_label",),
                )

    def _draw_camera_gizmo(self, canvas: object) -> None:
        width = max(1, int(canvas.winfo_width()))  # type: ignore[attr-defined]
        x = width - 70
        y = 42
        canvas.create_oval(
            x - 12,
            y - 12,
            x + 12,
            y + 12,
            fill="#1e293b",
            outline="#94a3b8",
            tags=("camera_gizmo",),
        )
        canvas.create_line(
            x,
            y,
            x,
            y - 30,
            fill="#22c55e",
            width=2,
            arrow="last",
            tags=("camera_gizmo",),
        )
        canvas.create_line(
            x,
            y,
            x - 36,
            y,
            fill="#ef4444",
            width=2,
            arrow="last",
            tags=("camera_gizmo",),
        )
        canvas.create_line(
            x,
            y,
            x + 36,
            y,
            fill="#38bdf8",
            width=2,
            arrow="last",
            tags=("camera_gizmo",),
        )
        canvas.create_text(
            x,
            y - 40,
            text="Z",
            fill="#22c55e",
            font=("Helvetica", 10, "bold"),
            tags=("camera_gizmo",),
        )
        canvas.create_text(
            x - 46,
            y,
            text="X",
            fill="#ef4444",
            font=("Helvetica", 10, "bold"),
            tags=("camera_gizmo",),
        )
        canvas.create_text(
            x + 46,
            y,
            text="Y",
            fill="#38bdf8",
            font=("Helvetica", 10, "bold"),
            tags=("camera_gizmo",),
        )

    @staticmethod
    def _bool_text(value: bool, language: str) -> str:
        return translate("yes" if value else "no", language)

    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        total_seconds = max(0, int(seconds))
        minutes, second = divmod(total_seconds, 60)
        hour, minute = divmod(minutes, 60)
        return f"{hour:02d}:{minute:02d}:{second:02d}"

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
