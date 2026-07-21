from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from physical_ai_sandbox.paths import DEFAULT_SCHEMA_PATH


def load_yaml(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a YAML mapping: {config_path}")
    return data


def load_schema(path: str | Path = DEFAULT_SCHEMA_PATH) -> dict[str, Any]:
    schema_path = Path(path)
    with schema_path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Schema must be a JSON object: {schema_path}")
    return data


def validate_config(config: dict[str, Any], schema_path: str | Path = DEFAULT_SCHEMA_PATH) -> None:
    schema = load_schema(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(config), key=lambda error: list(error.path))
    if errors:
        messages = []
        for error in errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            messages.append(f"{location}: {error.message}")
        raise ValueError("Invalid scene config:\n" + "\n".join(messages))


def load_and_validate_config(
    config_path: str | Path,
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    config = load_yaml(config_path)
    validate_config(config, schema_path)
    return config
