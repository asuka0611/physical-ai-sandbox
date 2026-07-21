from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_macos_packaging_files_do_not_embed_user_absolute_path() -> None:
    scanned = [
        ROOT / "packaging" / "macos" / "setup.py",
        ROOT / "packaging" / "macos" / "app_runtime.py",
        ROOT / "scripts" / "build_macos_app.sh",
        ROOT / "scripts" / "run_bundled_app.sh",
    ]

    for path in scanned:
        text = path.read_text(encoding="utf-8")
        assert ("/Users/" + "miyachiasuka") not in text


def test_macos_build_scripts_reference_expected_app_name() -> None:
    text = (ROOT / "scripts" / "build_macos_app.sh").read_text(encoding="utf-8")

    assert "Physical AI Sandbox.app" in text
    assert "codesign --force --deep --sign -" in text
