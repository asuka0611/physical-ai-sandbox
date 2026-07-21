from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from pathlib import Path
from types import SimpleNamespace

from physical_ai_sandbox.app.paths import build_app_paths, bundle_resources_dir
from physical_ai_sandbox.paths import _resolve_package_root


def test_development_resource_paths_resolve_existing_config_and_schema(tmp_path: Path) -> None:
    paths = build_app_paths(home=tmp_path)

    assert paths.bundled_default_config.exists()
    assert paths.bundled_schema.exists()
    assert paths.resolve_config() == paths.bundled_default_config


def test_required_bundle_resource_list_is_relative_to_resources(tmp_path: Path) -> None:
    resources = tmp_path / "Resources"
    (resources / "configs").mkdir(parents=True)
    (resources / "schemas").mkdir()
    (resources / "docs").mkdir()
    (resources / "configs" / "default.yaml").write_text("scene: {}\n")
    (resources / "schemas" / "scene_config.schema.json").write_text("{}\n")
    (resources / "docs" / "UI_GUIDE_JA.md").write_text("# ui\n")
    (resources / "docs" / "MACOS_APP_GUIDE_JA.md").write_text("# app\n")
    paths = build_app_paths(home=tmp_path / "home", resources_dir=resources)

    assert all(path.is_absolute() for path in paths.required_bundle_resources())
    assert all(path.exists() for path in paths.required_bundle_resources())


def test_bundled_resource_path_searches_up_from_nested_executable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    resources = tmp_path / "Physical AI Sandbox.app" / "Contents" / "Resources"
    (resources / "configs").mkdir(parents=True)
    (resources / "configs" / "default.yaml").write_text("scene: {}\n")
    nested_executable = resources / "lib" / "python3.12" / "app_entry.py"
    nested_executable.parent.mkdir(parents=True)
    nested_executable.write_text("# entry\n")

    monkeypatch.delenv("PHYSICAL_AI_SANDBOX_RESOURCES", raising=False)

    assert bundle_resources_dir(nested_executable) == resources.resolve()


def test_app_version_falls_back_to_bundled_pyproject(tmp_path: Path, monkeypatch) -> None:
    from physical_ai_sandbox.app import launcher

    resources = tmp_path / "Resources"
    resources.mkdir()
    (resources / "pyproject.toml").write_text('[project]\nversion = "0.2.0"\n')

    def missing_distribution(_name: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(launcher, "version", missing_distribution)
    monkeypatch.setattr(
        launcher,
        "build_app_paths",
        lambda: SimpleNamespace(resources_dir=resources),
    )

    assert launcher.app_version() == "0.2.0"


def test_shared_package_root_detects_macos_bundle_resources(tmp_path: Path) -> None:
    resources = tmp_path / "Physical AI Sandbox.app" / "Contents" / "Resources"
    package_dir = resources / "lib" / "python3.12" / "physical_ai_sandbox"
    (resources / "configs").mkdir(parents=True)
    (resources / "configs" / "default.yaml").write_text("scene: {}\n")
    package_dir.mkdir(parents=True)
    paths_file = package_dir / "paths.py"
    paths_file.write_text("# bundled paths\n")

    assert _resolve_package_root(paths_file) == resources
