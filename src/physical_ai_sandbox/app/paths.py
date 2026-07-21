from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from physical_ai_sandbox.app import APP_DISPLAY_NAME
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH, DEFAULT_SCHEMA_PATH, PACKAGE_ROOT


@dataclass(frozen=True, slots=True)
class AppPaths:
    bundled: bool
    resources_dir: Path
    app_support_dir: Path
    config_dir: Path
    logs_dir: Path
    datasets_dir: Path
    models_dir: Path
    replays_dir: Path
    crash_reports_dir: Path
    bundled_default_config: Path
    bundled_schema: Path
    user_config: Path

    def ensure_writable_dirs(self) -> None:
        for path in [
            self.app_support_dir,
            self.config_dir,
            self.logs_dir,
            self.datasets_dir,
            self.models_dir,
            self.replays_dir,
            self.crash_reports_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def ensure_first_launch_config(self) -> Path:
        self.ensure_writable_dirs()
        if not self.user_config.exists():
            shutil.copy2(self.bundled_default_config, self.user_config)
        return self.user_config

    def resolve_config(self, cli_config: str | Path | None = None) -> Path:
        if cli_config is not None:
            return Path(cli_config).expanduser().resolve()
        if self.user_config.exists():
            return self.user_config
        return self.bundled_default_config

    def required_bundle_resources(self) -> list[Path]:
        return [
            self.bundled_default_config,
            self.bundled_schema,
            self.resources_dir / "docs" / "UI_GUIDE_JA.md",
            self.resources_dir / "docs" / "MACOS_APP_GUIDE_JA.md",
        ]


def is_bundled_app() -> bool:
    return bool(getattr(sys, "frozen", False)) and sys.platform == "darwin"


def bundle_resources_dir(executable: Path | None = None) -> Path:
    explicit = os.environ.get("PHYSICAL_AI_SANDBOX_RESOURCES")
    if explicit:
        return Path(explicit).expanduser().resolve()

    seeds = [Path(executable or sys.executable), PACKAGE_ROOT]
    if sys.argv:
        seeds.append(Path(sys.argv[0]))
    for seed in seeds:
        resolved = seed.resolve()
        for parent in (resolved, *resolved.parents):
            if parent.name == "Resources" and (parent / "configs" / "default.yaml").exists():
                return parent
            resources = parent / "Resources"
            if (resources / "configs" / "default.yaml").exists():
                return resources

    if is_bundled_app():
        exe = Path(executable or sys.executable).resolve()
        return exe.parents[1] / "Resources"
    return PACKAGE_ROOT


def app_support_dir(home: Path | None = None) -> Path:
    explicit = os.environ.get("PHYSICAL_AI_SANDBOX_APP_SUPPORT")
    if explicit and home is None:
        return Path(explicit).expanduser()
    base_home = home or Path(os.environ.get("PHYSICAL_AI_SANDBOX_HOME", Path.home()))
    return base_home / "Library" / "Application Support" / APP_DISPLAY_NAME


def build_app_paths(home: Path | None = None, resources_dir: Path | None = None) -> AppPaths:
    resources = (resources_dir or bundle_resources_dir()).resolve()
    support = app_support_dir(home)
    bundled = is_bundled_app() or resources != PACKAGE_ROOT
    bundled_config = resources / "configs" / "default.yaml"
    bundled_schema = resources / "schemas" / "scene_config.schema.json"
    if not bundled_config.exists() and not bundled:
        bundled_config = DEFAULT_CONFIG_PATH
    if not bundled_schema.exists() and not bundled:
        bundled_schema = DEFAULT_SCHEMA_PATH
    config_dir = support / "configs"
    return AppPaths(
        bundled=bundled,
        resources_dir=resources,
        app_support_dir=support,
        config_dir=config_dir,
        logs_dir=support / "logs",
        datasets_dir=support / "datasets",
        models_dir=support / "models",
        replays_dir=support / "replays",
        crash_reports_dir=support / "crash-reports",
        bundled_default_config=bundled_config,
        bundled_schema=bundled_schema,
        user_config=config_dir / "default.yaml",
    )


def mask_home(path: str | Path, home: Path | None = None) -> str:
    raw = str(path)
    home_path = str(home or Path.home())
    if home_path and raw.startswith(home_path):
        return raw.replace(home_path, "~", 1)
    return raw
