from __future__ import annotations

import argparse
import os
import platform
import sys
import tomllib
import traceback
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import NoReturn

from physical_ai_sandbox.app import APP_DISPLAY_NAME, APP_PHASE
from physical_ai_sandbox.app.paths import build_app_paths, mask_home
from physical_ai_sandbox.app.process_manager import build_runtime_process


def app_version() -> str:
    try:
        return version("physical-ai-sandbox")
    except PackageNotFoundError:
        pyproject = build_app_paths().resources_dir / "pyproject.toml"
        if pyproject.exists():
            return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
        return "0.0.0"



def configure_bundled_tk(app_paths) -> None:  # type: ignore[no-untyped-def]
    tcl_library = app_paths.resources_dir / "lib" / "tcl9.0"
    tk_library = app_paths.resources_dir / "lib" / "tk9.0"
    if tcl_library.exists():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_library))
    if tk_library.exists():
        os.environ.setdefault("TK_LIBRARY", str(tk_library))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"{APP_DISPLAY_NAME} macOS launcher")
    parser.add_argument("--role", choices=["launcher", "runtime"], default="launcher")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--language", choices=["ja", "en"], default="ja")
    parser.add_argument("--no-viewer", action="store_true")
    return parser


def run_launcher(args: argparse.Namespace) -> int:
    app_paths = build_app_paths()
    configure_bundled_tk(app_paths)
    app_paths.ensure_first_launch_config()
    config_path = app_paths.resolve_config(args.config)
    if app_paths.bundled:
        runtime_args = argparse.Namespace(
            role="runtime",
            config=config_path,
            language=args.language,
            no_viewer=args.no_viewer,
        )
        return run_runtime(runtime_args)

    process = build_runtime_process(app_paths, config_path=config_path, language=args.language)
    try:
        child = process.start()
        return child.wait()
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        write_crash_report(app_paths.crash_reports_dir, exc, args)
        show_error_dialog("予期しないエラーが発生しました", str(exc))
        return 1
    finally:
        process.terminate_tree(timeout=5.0)


def run_runtime(args: argparse.Namespace) -> int:
    from physical_ai_sandbox.ui.control_panel import run_control_panel

    app_paths = build_app_paths()
    configure_bundled_tk(app_paths)
    app_paths.ensure_first_launch_config()
    config_path = app_paths.resolve_config(args.config)
    try:
        run_control_panel(
            config_path=config_path,
            language=args.language,
            show_viewer=not args.no_viewer,
        )
    except Exception as exc:
        app_paths = build_app_paths()
        write_crash_report(app_paths.crash_reports_dir, exc, args)
        show_error_dialog("Viewerを起動できませんでした", str(exc))
        return 1
    return 0


def write_crash_report(crash_dir: Path, exc: BaseException, args: argparse.Namespace) -> Path:
    crash_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    path = crash_dir / f"crash_{timestamp}.log"
    masked_args = [mask_home(value) for value in sys.argv]
    content = "\n".join(
        [
            f"app: {APP_DISPLAY_NAME}",
            f"version: {app_version()}",
            f"phase: {APP_PHASE}",
            f"macos: {platform.mac_ver()[0] or 'unknown'}",
            f"architecture: {platform.machine()}",
            f"python: {platform.python_version()}",
            f"argv: {masked_args}",
            f"config: {mask_home(args.config) if args.config else '<default>'}",
            f"error: {exc.__class__.__name__}: {exc}",
            "traceback:",
            "".join(traceback.format_exception(exc)),
        ],
    )
    path.write_text(content, encoding="utf-8")
    return path


def show_error_dialog(title: str, message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        print(f"{title}: {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.role == "runtime":
        return run_runtime(args)
    return run_launcher(args)


def main_no_return() -> NoReturn:
    raise SystemExit(main())
