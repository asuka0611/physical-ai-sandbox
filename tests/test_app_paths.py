from __future__ import annotations

from pathlib import Path

from physical_ai_sandbox.app.paths import build_app_paths, mask_home


def test_application_support_paths_are_created_under_home(tmp_path: Path) -> None:
    paths = build_app_paths(home=tmp_path)

    assert paths.app_support_dir == (
        tmp_path / "Library" / "Application Support" / "Physical AI Sandbox"
    )
    assert paths.config_dir == paths.app_support_dir / "configs"
    assert paths.logs_dir == paths.app_support_dir / "logs"
    assert paths.crash_reports_dir == paths.app_support_dir / "crash-reports"


def test_mask_home_removes_full_home_path(tmp_path: Path) -> None:
    path = tmp_path / "Library" / "Application Support" / "Physical AI Sandbox"

    assert mask_home(path, home=tmp_path).startswith("~/")
