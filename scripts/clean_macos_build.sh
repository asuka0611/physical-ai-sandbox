#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

rm -rf build "dist/Physical AI Sandbox.app" "dist/Physical AI Sandbox Launcher.app"
find packaging/macos -maxdepth 1 -type d -name "*.egg-info" -prune -exec rm -rf {} +

echo "Cleaned macOS build artifacts."
