# macOS Launcher Guide JA

## 概要

`Physical AI Sandbox Launcher.app` は配布用アプリではありません。このMac上のローカル開発環境を起動するためのLauncherです。

ダブルクリックすると、Terminalウィンドウを開かずに以下と同等の処理を実行します。

```bash
cd "/Users/miyachiasuka/Documents/prog/Physical AI Sandbox"
uv run mjpython scripts/run_control_panel.py
```

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

初回起動時、macOSがプロジェクトフォルダへのアクセス許可を求める場合があります。その場合は `/Users/miyachiasuka/Documents/prog/Physical AI Sandbox` を選択してください。

## ログ

```text
~/Library/Logs/Physical AI Sandbox Launcher/
```

起動失敗時は日本語ダイアログにエラー内容とログパスを表示します。

## 注意

このLauncherはPython、MuJoCo、依存関係、Dataset、Checkpointを同梱しません。Developer ID署名、notarization、Intel対応、配布用パッケージングは対象外です。
