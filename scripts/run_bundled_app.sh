#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_PATH="$ROOT_DIR/dist/Physical AI Sandbox Launcher.app"

if [ ! -d "$APP_PATH" ]; then
  echo "Launcher app not found: $APP_PATH" >&2
  exit 1
fi

open -n "$APP_PATH"
