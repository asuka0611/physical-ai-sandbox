from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_py2app_paths() -> None:
    resources = Path(__file__).resolve().parent
    candidates: list[Path] = [resources]
    candidates.extend(sorted((resources / "lib").glob("python*")))
    candidates.extend(sorted((resources / "lib").glob("python*/site-packages")))
    candidates.extend(sorted((resources / "lib").glob("python*.zip")))
    for candidate in reversed(candidates):
        if candidate.exists():
            sys.path.insert(0, str(candidate))


_bootstrap_py2app_paths()

from physical_ai_sandbox.app.launcher import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
