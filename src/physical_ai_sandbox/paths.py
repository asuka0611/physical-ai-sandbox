from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "configs" / "default.yaml"
DEFAULT_SCHEMA_PATH = PACKAGE_ROOT / "schemas" / "scene_config.schema.json"
