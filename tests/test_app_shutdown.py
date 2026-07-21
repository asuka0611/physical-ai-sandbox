from __future__ import annotations

import sys
from pathlib import Path

from physical_ai_sandbox.app.process_manager import ManagedProcess


def test_shutdown_is_idempotent_for_not_started_process(tmp_path: Path) -> None:
    process = ManagedProcess(command=[sys.executable, "-c", ""], env={}, cwd=tmp_path)

    assert process.terminate_tree() is None


def test_shutdown_after_child_already_exited_returns_code(tmp_path: Path) -> None:
    process = ManagedProcess(
        command=[sys.executable, "-c", "raise SystemExit(3)"],
        env={},
        cwd=tmp_path,
    )
    child = process.start()
    child.wait(timeout=5.0)

    assert process.terminate_tree() == 3
