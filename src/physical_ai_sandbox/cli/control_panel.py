from __future__ import annotations

import argparse
from pathlib import Path

from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH
from physical_ai_sandbox.ui.control_panel import run_control_panel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the Physical AI Sandbox control panel.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--language", choices=["ja", "en"], default=None)
    parser.add_argument(
        "--no-viewer",
        action="store_true",
        help="Run the panel without MuJoCo Viewer.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_control_panel(
        config_path=args.config,
        language=args.language,
        show_viewer=not args.no_viewer,
    )
    return 0
