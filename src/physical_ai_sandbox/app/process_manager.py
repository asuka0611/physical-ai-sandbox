from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from physical_ai_sandbox.app.paths import AppPaths


@dataclass(slots=True)
class ManagedProcess:
    command: list[str]
    env: dict[str, str]
    cwd: Path
    process: subprocess.Popen[str] | None = field(default=None, init=False)

    def start(self) -> subprocess.Popen[str]:
        if self.process is not None and self.process.poll() is None:
            return self.process
        self.process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            env=self.env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
        )
        return self.process

    def terminate_tree(self, timeout: float = 5.0) -> int | None:
        if self.process is None:
            return None
        if self.process.poll() is not None:
            return self.process.returncode
        self.process.terminate()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                return self.process.returncode
            time.sleep(0.05)
        self.process.kill()
        return self.process.wait(timeout=2.0)


def resolve_mjpython(app_paths: AppPaths) -> Path | None:
    bundled = app_paths.resources_dir / "bin" / "mjpython"
    if bundled.exists():
        return bundled
    found = shutil.which("mjpython")
    if found:
        return Path(found)
    return None


def runtime_command(app_paths: AppPaths, *, config_path: Path, language: str = "ja") -> list[str]:
    if app_paths.bundled:
        app_executable = app_paths.resources_dir.parent / "MacOS" / "Physical AI Sandbox"
        return [
            str(app_executable if app_executable.exists() else Path(sys.executable)),
            "--role",
            "runtime",
            "--config",
            str(config_path),
            "--language",
            language,
        ]
    mjpython = resolve_mjpython(app_paths)
    if mjpython is not None:
        return [
            str(mjpython),
            "-m",
            "physical_ai_sandbox.app.main",
            "--role",
            "runtime",
            "--config",
            str(config_path),
            "--language",
            language,
        ]
    return [
        sys.executable,
        "-m",
        "physical_ai_sandbox.app.main",
        "--role",
        "runtime",
        "--config",
        str(config_path),
        "--language",
        language,
    ]


def runtime_environment(app_paths: AppPaths) -> dict[str, str]:
    env = os.environ.copy()
    env["PHYSICAL_AI_SANDBOX_APP_SUPPORT"] = str(app_paths.app_support_dir)
    env["PHYSICAL_AI_SANDBOX_RESOURCES"] = str(app_paths.resources_dir)
    env.setdefault("PYTHONUNBUFFERED", "1")
    tcl_library = app_paths.resources_dir / "lib" / "tcl9.0"
    tk_library = app_paths.resources_dir / "lib" / "tk9.0"
    if tcl_library.exists():
        env.setdefault("TCL_LIBRARY", str(tcl_library))
    if tk_library.exists():
        env.setdefault("TK_LIBRARY", str(tk_library))
    mjpython = resolve_mjpython(app_paths)
    if mjpython is not None:
        env.setdefault("MJPYTHON_BIN", str(mjpython))
    return env


def build_runtime_process(
    app_paths: AppPaths,
    *,
    config_path: Path,
    language: str = "ja",
) -> ManagedProcess:
    return ManagedProcess(
        command=runtime_command(app_paths, config_path=config_path, language=language),
        env=runtime_environment(app_paths),
        cwd=app_paths.app_support_dir,
    )
