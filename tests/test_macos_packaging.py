from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_macos_build_script_creates_local_launcher_app() -> None:
    text = (ROOT / "scripts" / "build_macos_app.sh").read_text(encoding="utf-8")

    assert "Physical AI Sandbox Launcher.app" in text
    assert "swiftc" in text
    assert "LocalLauncher.swift" in text
    assert "py2app" not in text
    assert "codesign" not in text


def test_local_launcher_runs_existing_control_panel_without_terminal() -> None:
    text = (ROOT / "packaging" / "macos" / "LocalLauncher.swift").read_text(
        encoding="utf-8"
    )

    assert "/Users/miyachiasuka/Documents/prog/Physical AI Sandbox" in text
    assert "uv run python scripts/run_control_panel.py" in text
    assert "launchctl" in text
    assert "LaunchAgent" in text or "launch agent" in text
    assert "NSAlert" in text
    assert "Terminal" not in text


def test_local_launcher_writes_logs_and_reports_japanese_errors() -> None:
    text = (ROOT / "packaging" / "macos" / "LocalLauncher.swift").read_text(
        encoding="utf-8"
    )

    assert "Library/Logs/Physical AI Sandbox Launcher" in text
    assert "latest.log" in text
    assert "Physical AI Sandbox の起動に失敗しました。" in text
    assert "プロジェクトフォルダ" in text


def test_launcher_prevents_duplicate_control_panel_processes() -> None:
    text = (ROOT / "packaging" / "macos" / "LocalLauncher.swift").read_text(
        encoding="utf-8"
    )

    assert "existingControlPanelPID" in text
    assert "run_control_panel.py" in text
    assert "既に起動中です" in text
    assert "control-panel.pid" in text
    assert "bootout" in text
    assert "bootstrap" in text


def test_launcher_app_is_local_only_and_not_self_contained() -> None:
    text = (ROOT / "scripts" / "build_macos_app.sh").read_text(encoding="utf-8")

    assert "PhysicalAISandboxLauncher" in text
    assert "Contents/MacOS" in text
    assert "uv" not in text
    assert "mjpython" not in text
    assert "site-packages" not in text


def test_run_script_references_launcher_app() -> None:
    text = (ROOT / "scripts" / "run_bundled_app.sh").read_text(encoding="utf-8")

    assert "Physical AI Sandbox Launcher.app" in text
    assert "open -n" in text
