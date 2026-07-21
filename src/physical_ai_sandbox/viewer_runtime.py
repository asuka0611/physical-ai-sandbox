from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def mjpython_path() -> str:
    mjpython = shutil.which("mjpython")
    if mjpython is None:
        raise RuntimeError(
            "MuJoCo viewer on macOS requires mjpython, but mjpython was not found. "
            "Run `uv sync` and then `uv run mjpython <script>`.",
        )
    return mjpython


def require_mjpython_on_macos() -> None:
    if sys.platform != "darwin":
        return
    if Path(sys.executable).name == "mjpython" or os.environ.get("MJPYTHON_BIN"):
        return
    raise RuntimeError(
        "MuJoCo viewer on macOS must be launched with mjpython. "
        "Run `uv run mjpython scripts/run_manual.py`.",
    )
