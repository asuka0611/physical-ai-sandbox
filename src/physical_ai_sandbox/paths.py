from __future__ import annotations

from pathlib import Path


def _resolve_package_root(file_path: Path) -> Path:
    resolved = file_path.resolve()
    for parent in resolved.parents:
        if parent.name == "Resources" and (parent / "configs" / "default.yaml").exists():
            return parent
    return resolved.parents[2]


PACKAGE_ROOT = _resolve_package_root(Path(__file__))
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "configs" / "default.yaml"
DEFAULT_SCHEMA_PATH = PACKAGE_ROOT / "schemas" / "scene_config.schema.json"
