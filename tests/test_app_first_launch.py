from __future__ import annotations

import argparse
from pathlib import Path

from physical_ai_sandbox.app.paths import build_app_paths


def test_first_launch_copies_default_config_once(tmp_path: Path) -> None:
    resources = tmp_path / "Resources"
    (resources / "configs").mkdir(parents=True)
    (resources / "schemas").mkdir()
    bundled_config = resources / "configs" / "default.yaml"
    bundled_config.write_text("value: bundled\n")
    (resources / "schemas" / "scene_config.schema.json").write_text("{}\n")
    paths = build_app_paths(home=tmp_path / "home", resources_dir=resources)

    copied = paths.ensure_first_launch_config()
    assert copied.read_text() == "value: bundled\n"

    copied.write_text("value: user\n")
    assert paths.ensure_first_launch_config().read_text() == "value: user\n"


def test_cli_config_has_priority_over_user_and_bundle_config(tmp_path: Path) -> None:
    paths = build_app_paths(home=tmp_path)
    cli_config = tmp_path / "custom.yaml"
    cli_config.write_text("custom: true\n")

    assert paths.resolve_config(cli_config) == cli_config.resolve()


def test_runtime_resolves_default_config_when_cli_config_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from physical_ai_sandbox.app.launcher import run_runtime
    from physical_ai_sandbox.ui import control_panel

    captured: dict[str, object] = {}

    def fake_run_control_panel(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setenv("PHYSICAL_AI_SANDBOX_HOME", str(tmp_path))
    monkeypatch.setattr(control_panel, "run_control_panel", fake_run_control_panel)

    result = run_runtime(
        argparse.Namespace(config=None, language="ja", no_viewer=True, role="runtime"),
    )

    assert result == 0
    config_path = captured["config_path"]
    assert isinstance(config_path, Path)
    assert config_path.exists()
    assert config_path.name == "default.yaml"
    assert captured["show_viewer"] is False



def test_bundled_launcher_runs_runtime_in_process(tmp_path: Path, monkeypatch) -> None:
    from physical_ai_sandbox.app import launcher

    resources = tmp_path / "Physical AI Sandbox.app" / "Contents" / "Resources"
    (resources / "configs").mkdir(parents=True)
    (resources / "schemas").mkdir()
    (resources / "configs" / "default.yaml").write_text("value: bundled\n")
    (resources / "schemas" / "scene_config.schema.json").write_text("{}\n")
    paths = build_app_paths(home=tmp_path / "home", resources_dir=resources)
    captured: dict[str, object] = {}

    def fake_run_runtime(runtime_args: argparse.Namespace) -> int:
        captured.update(vars(runtime_args))
        return 7

    def fail_build_runtime_process(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("bundled launcher should not spawn a child process")

    monkeypatch.setattr(launcher, "build_app_paths", lambda: paths)
    monkeypatch.setattr(launcher, "configure_bundled_tk", lambda _paths: None)
    monkeypatch.setattr(launcher, "run_runtime", fake_run_runtime)
    monkeypatch.setattr(launcher, "build_runtime_process", fail_build_runtime_process)

    result = launcher.run_launcher(
        argparse.Namespace(config=None, language="ja", no_viewer=True, role="launcher"),
    )

    assert result == 7
    assert captured["role"] == "runtime"
    assert captured["language"] == "ja"
    assert captured["no_viewer"] is True
    assert isinstance(captured["config"], Path)
    assert captured["config"].name == "default.yaml"
