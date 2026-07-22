from __future__ import annotations

import contextlib
import sys
import tomllib
from pathlib import Path

from setuptools import setup

ROOT = Path(__file__).resolve().parents[2]
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())
APP_VERSION = PROJECT["project"]["version"]
sys.path.insert(0, str(ROOT / "src"))

APP = [str(ROOT / "packaging" / "macos" / "app_entry.py")]
DATA_FILES = [
    ("configs", [str(ROOT / "configs" / "default.yaml")]),
    ("schemas", [str(ROOT / "schemas" / "scene_config.schema.json")]),
    (
        "docs",
        [
            str(ROOT / "docs" / "UI_GUIDE_JA.md"),
            str(ROOT / "docs" / "UI_GUIDE_EN.md"),
            str(ROOT / "docs" / "MACOS_APP_GUIDE_JA.md"),
            str(ROOT / "docs" / "MACOS_APP_GUIDE_EN.md"),
        ],
    ),
    ("", [str(ROOT / "packaging" / "macos" / "app_runtime.py"), str(ROOT / "pyproject.toml")]),
]

icon_file = ROOT / "assets" / "app-icon" / "PhysicalAISandbox.icns"

OPTIONS = {
    "argv_emulation": False,
    "packages": [
        "physical_ai_sandbox",
        "mujoco",
        "numpy",
        "yaml",
        "jsonschema",
        "glfw",
        "OpenGL",
        "tkinter",
    ],
    "includes": [
        "physical_ai_sandbox.app.main",
        "physical_ai_sandbox.app.launcher",
        "physical_ai_sandbox.ui.control_panel",
    ],
    "excludes": ["tests"],
    "iconfile": str(icon_file) if icon_file.exists() else None,
    "plist": {
        "CFBundleName": "Physical AI Sandbox",
        "CFBundleDisplayName": "Physical AI Sandbox",
        "CFBundleIdentifier": "com.asuka0611.physicalaisandbox",
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "LSMinimumSystemVersion": "14.0",
        "LSApplicationCategoryType": "public.app-category.education",
        "NSHighResolutionCapable": True,
    },
}

if OPTIONS["iconfile"] is None:
    del OPTIONS["iconfile"]

# uv standalone CPython can expose zlib as a built-in module without __file__.
# py2app 0.28 still assumes a file-backed zlib extension; skip that optional
# copy when zlib is built into the interpreter.
def _patch_py2app_builtin_zlib() -> None:
    import zlib

    if hasattr(zlib, "__file__"):
        return
    try:
        from py2app import build_app as py2app_build_app
    except Exception:
        return

    original = py2app_build_app.py2app.build_executable

    def patched(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        zlib.__file__ = str(ROOT / "packaging" / "macos" / "app_runtime.py")
        try:
            return original(self, *args, **kwargs)
        finally:
            with contextlib.suppress(AttributeError):
                delattr(zlib, "__file__")

    py2app_build_app.py2app.build_executable = patched


_patch_py2app_builtin_zlib()

setup(
    name="Physical AI Sandbox",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
)
