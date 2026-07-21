from __future__ import annotations

import sys
from pathlib import Path

from physical_ai_sandbox.app.paths import build_app_paths
from physical_ai_sandbox.app.process_manager import ManagedProcess, runtime_command


def test_managed_process_exits_normally(tmp_path: Path) -> None:
    process = ManagedProcess(
        command=[sys.executable, "-c", "print('ready')"],
        env={},
        cwd=tmp_path,
    )

    child = process.start()
    assert child.wait(timeout=5.0) == 0
    assert process.terminate_tree() == 0


def test_managed_process_kills_after_timeout(tmp_path: Path) -> None:
    process = ManagedProcess(
        command=[sys.executable, "-c", "import time; time.sleep(30)"],
        env={},
        cwd=tmp_path,
    )

    process.start()
    return_code = process.terminate_tree(timeout=0.1)

    assert return_code is not None


def test_development_runtime_command_uses_safe_entrypoint(tmp_path: Path) -> None:
    paths = build_app_paths(home=tmp_path)
    command = runtime_command(paths, config_path=paths.bundled_default_config, language="ja")

    assert "physical_ai_sandbox.app.main" in command
    assert "--role" in command
    assert "runtime" in command
    assert command[0].endswith(("mjpython", "python", "python3"))


def test_bundled_runtime_command_uses_app_executable_child(tmp_path: Path) -> None:
    resources = tmp_path / "Physical AI Sandbox.app" / "Contents" / "Resources"
    macos = tmp_path / "Physical AI Sandbox.app" / "Contents" / "MacOS"
    (resources / "configs").mkdir(parents=True)
    macos.mkdir(parents=True)
    app_executable = macos / "Physical AI Sandbox"
    app_executable.write_text("#!/bin/sh\n")
    paths = build_app_paths(home=tmp_path / "home", resources_dir=resources)

    command = runtime_command(paths, config_path=resources / "configs" / "default.yaml")

    assert command[0] == str(app_executable)
    assert "--role" in command
    assert "runtime" in command
