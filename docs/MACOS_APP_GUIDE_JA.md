# macOS App Guide JA

## 対応環境

- macOS 14以降
- Apple Siliconを第一対象
- Intel Macは未検証

## ビルド

```bash
bash scripts/clean_macos_build.sh
bash scripts/build_macos_app.sh
```

出力:

```text
dist/Physical AI Sandbox.app
```

## 起動

Finderで `dist/Physical AI Sandbox.app` をダブルクリックするか、以下を実行します。

```bash
open "dist/Physical AI Sandbox.app"
```

または:

```bash
bash scripts/run_bundled_app.sh
```

## 初回起動

初回起動時に以下の場所を作成します。

```text
~/Library/Application Support/Physical AI Sandbox/
```

作成される主なディレクトリ:

- `configs/`
- `logs/`
- `datasets/`
- `models/`
- `replays/`
- `crash-reports/`

`configs/default.yaml` が存在しない場合、アプリ内のdefault configからコピーします。

## 設定ファイル

設定ファイルの優先順:

1. CLIで指定されたconfig
2. Application Support内の `configs/default.yaml`
3. app bundle内の `configs/default.yaml`

## ログ

アプリ実行時のログとEpisode記録はApplication Support配下に保存されます。クラッシュログは以下です。

```text
~/Library/Application Support/Physical AI Sandbox/crash-reports/
```

## macOSセキュリティ警告

Phase 4.6ではAd Hoc署名のみです。初回起動時にGatekeeper警告が出る可能性があります。

配布段階ではDeveloper ID Application署名、Hardened Runtime、notarization、staplingが必要です。

## アンインストール

アプリ本体を削除し、必要に応じて以下も削除します。

```text
~/Library/Application Support/Physical AI Sandbox/
```

## MuJoCo制約

macOSのMuJoCo Viewerは通常`mjpython`相当のtrampolineが必要です。Phase 4.6の配布用`.app`ではLaunchServices経由の子アプリ実行による署名問題を避けるため、バンドル起動時は同一プロセスでcontrol panel/runtimeを実行します。開発環境の起動スクリプトでは引き続き`mjpython`を優先します。
