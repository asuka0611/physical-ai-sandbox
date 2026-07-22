#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_PATH="$ROOT_DIR/dist/Physical AI Sandbox Launcher.app"
SWIFT_SOURCE="$ROOT_DIR/packaging/macos/LocalLauncher.swift"
ICON_PATH="$ROOT_DIR/assets/app-icon/PhysicalAISandbox.icns"
EXECUTABLE_PATH="$APP_PATH/Contents/MacOS/PhysicalAISandboxLauncher"

cd "$ROOT_DIR"

if ! command -v swiftc >/dev/null 2>&1; then
  echo "swiftc was not found. This launcher can only be built on macOS with Xcode Command Line Tools." >&2
  exit 1
fi

mkdir -p "$APP_PATH/Contents/MacOS" "$APP_PATH/Contents/Resources"
rm -rf "$APP_PATH"
mkdir -p "$APP_PATH/Contents/MacOS" "$APP_PATH/Contents/Resources"

swiftc "$SWIFT_SOURCE" -o "$EXECUTABLE_PATH" -framework Cocoa
chmod +x "$EXECUTABLE_PATH"

if [ -f "$ICON_PATH" ]; then
  cp "$ICON_PATH" "$APP_PATH/Contents/Resources/PhysicalAISandbox.icns"
fi

cat > "$APP_PATH/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>ja</string>
  <key>CFBundleDisplayName</key>
  <string>Physical AI Sandbox Launcher</string>
  <key>CFBundleExecutable</key>
  <string>PhysicalAISandboxLauncher</string>
  <key>CFBundleIconFile</key>
  <string>PhysicalAISandbox.icns</string>
  <key>CFBundleIdentifier</key>
  <string>com.asuka0611.physical-ai-sandbox.launcher</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>Physical AI Sandbox Launcher</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.4.6</string>
  <key>CFBundleVersion</key>
  <string>0.4.6</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>NSDocumentsFolderUsageDescription</key>
  <string>Physical AI Sandbox Launcher needs access to the local project folder in Documents.</string>
</dict>
</plist>
PLIST

plutil -lint "$APP_PATH/Contents/Info.plist" >/dev/null
test -x "$EXECUTABLE_PATH"
if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$APP_PATH" >/dev/null
fi
echo "$APP_PATH"
