#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_PATH="$ROOT_DIR/dist/Physical AI Sandbox.app"
RESOURCES_DIR="$APP_PATH/Contents/Resources"
MACOS_DIR="$APP_PATH/Contents/MacOS"

cd "$ROOT_DIR"

uv run python scripts/generate_app_icon.py
(cd packaging/macos && uv run --with py2app --with "setuptools<72" python setup.py py2app --dist-dir "$ROOT_DIR/dist" --bdist-base "$ROOT_DIR/build")

mkdir -p "$RESOURCES_DIR/bin"
cat > "$RESOURCES_DIR/bin/mjpython" <<'EOF'
#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
RESOURCES_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
APP_ROOT="$(CDPATH= cd -- "$RESOURCES_DIR/.." && pwd)"
APP_EXE="$APP_ROOT/MacOS/Physical AI Sandbox"

MJPYTHON_NATIVE="$(find "$RESOURCES_DIR" -path '*/MuJoCo_(mjpython).app/Contents/MacOS/mjpython' -type f -perm -111 2>/dev/null | head -n 1 || true)"
if [ -z "$MJPYTHON_NATIVE" ]; then
  MJPYTHON_NATIVE="$(find "$RESOURCES_DIR" -path '*/MuJoCo_(mjpython).app/Contents/MacOS/mjpython' -type f 2>/dev/null | head -n 1 || true)"
fi
if [ -z "$MJPYTHON_NATIVE" ]; then
  echo "MuJoCo mjpython runtime was not found in the app bundle." >&2
  exit 127
fi

export MJPYTHON_BIN="$MJPYTHON_NATIVE"
export MJPYTHON_LIBPYTHON="$APP_EXE"
exec "$MJPYTHON_NATIVE" "$APP_EXE" "$@"
EOF
chmod +x "$RESOURCES_DIR/bin/mjpython"

cp packaging/macos/app_runtime.py "$RESOURCES_DIR/app_runtime.py"

PYTHON_BASE_PREFIX="$(uv run python -c 'import sys; print(sys.base_prefix)')"
PYTHON_BASE_LIB="$PYTHON_BASE_PREFIX/lib"
mkdir -p "$RESOURCES_DIR/lib"
for tk_lib in libtcl9.0.dylib libtcl9tk9.0.dylib; do
  if [ -f "$PYTHON_BASE_LIB/$tk_lib" ]; then
    cp "$PYTHON_BASE_LIB/$tk_lib" "$RESOURCES_DIR/lib/$tk_lib"
  fi
done
for tk_dir in tcl9 tcl9.0 tk9.0; do
  if [ -d "$PYTHON_BASE_LIB/$tk_dir" ]; then
    rm -rf "$RESOURCES_DIR/lib/$tk_dir"
    cp -R "$PYTHON_BASE_LIB/$tk_dir" "$RESOURCES_DIR/lib/$tk_dir"
  fi
done

MUJOCO_RESOURCE_DIR="$RESOURCES_DIR/lib/python3.12/mujoco"
if [ -d "$MUJOCO_RESOURCE_DIR" ] && command -v install_name_tool >/dev/null 2>&1; then
  while IFS= read -r binary_path; do
    case "$binary_path" in
      "$MUJOCO_RESOURCE_DIR"/plugin/*)
        mujoco_loader_path="@loader_path/../libmujoco.3.10.0.dylib"
        ;;
      *)
        mujoco_loader_path="@loader_path/libmujoco.3.10.0.dylib"
        ;;
    esac
    install_name_tool \
      -change "@rpath/mujoco.framework/Versions/A/libmujoco.3.10.0.dylib" \
      "$mujoco_loader_path" \
      "$binary_path" 2>/dev/null || true
    install_name_tool \
      -change "@rpath/libmujoco.3.10.0.dylib" \
      "$mujoco_loader_path" \
      "$binary_path" 2>/dev/null || true
  done < <(find "$MUJOCO_RESOURCE_DIR" \
    \( -name "*.dylib" -o -name "*.so" \) \
    -type f)
fi

if command -v plutil >/dev/null 2>&1; then
  plutil -remove PythonInfoDict.PythonExecutable "$APP_PATH/Contents/Info.plist" 2>/dev/null || true
fi

if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$APP_PATH"
fi

test -d "$APP_PATH"
echo "$APP_PATH"
