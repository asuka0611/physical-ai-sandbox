from __future__ import annotations

import argparse
from pathlib import Path

from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH
from physical_ai_sandbox.scene.config import load_and_validate_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Physical AI Sandbox scene config.")
    parser.add_argument("config", nargs="?", default=str(DEFAULT_CONFIG_PATH))
    args = parser.parse_args()
    config_path = Path(args.config)
    load_and_validate_config(config_path)
    print(f"Config valid: {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
