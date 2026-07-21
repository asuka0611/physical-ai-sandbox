# macOS Launcher Guide JA

## 概要

`Physical AI Sandbox Launcher.app` は配布用アプリではありません。このMac上のローカル開発環境を起動するためのLauncherです。

ダブルクリックすると、Terminalウィンドウを開かずに以下と同等の処理を実行します。

```bash
cd "/Users/miyachiasuka/Documents/prog/Physical AI Sandbox"
uv run python scripts/run_control_panel.py
```

操作パネルは通常Python/Tkinterで起動し、MuJoCo Viewerは別の `mjpython` simulation process で起動します。

## 必要条件

- プロジェクトが `/Users/miyachiasuka/Documents/prog/Physical AI Sandbox` に存在する
- `uv` がインストール済み
- `uv sync` が完了済み
- `uv run mjpython` が利用可能

## ビルド

```bash
bash scripts/clean_macos_build.sh
bash scripts/build_macos_app.sh
```

生成物:

```text
dist/Physical AI Sandbox Launcher.app
```

## 起動

```bash
open -n "dist/Physical AI Sandbox Launcher.app"
```

LauncherはユーザーLaunchAgentを使ってローカルUIを起動し、Launcher自身は起動後に終了します。二重起動時は既存の `run_control_panel.py` を検出し、新しいプロセスを増やしません。

## ログ

```text
~/Library/Logs/Physical AI Sandbox Launcher/
```

起動失敗時は日本語ダイアログにエラー内容とログパスを表示します。

## 注意

このLauncherはPython、MuJoCo、依存関係、Dataset、Checkpointを同梱しません。Developer ID署名、notarization、Intel対応、配布用パッケージングは対象外です。
