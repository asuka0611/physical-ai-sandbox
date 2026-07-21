# UI Guide JA

## 起動

日本語操作パネルとMuJoCo Viewerを同時に起動します。

```bash
uv run mjpython scripts/run_control_panel.py
```

英語表示で起動する場合:

```bash
uv run mjpython scripts/run_control_panel.py --language en
```

macOSではMuJoCo Viewerのために`mjpython`を使用してください。

## 操作パネル

- 実行状態、エピソード、ステップ、報酬、把持、持ち上げ、成功、記録状態を表示します。
- 言語メニューで日本語と英語を切り替えられます。
- `Start`、`Pause/Resume`、`Reset`、`Quit`で実行状態を制御します。
- `Start Recording`、`Stop Recording`でEpisode記録を開始・停止します。
- `Open Gripper`、`Close Gripper`でグリッパーを開閉します。
- XYZ操作ボタンは固定8次元Actionに変換されます。Observation、Action、Dataset仕様は変更していません。
- J1からJ7の`+` / `-`ボタンで7関節を直接操作できます。
- 操作量スライダーで1回の操作量を調整できます。

## キーボード

| Key | 操作 |
|---|---|
| W / S | 前後 |
| A / D | 左右 |
| R / F | 上下 |
| Q / E | 回転 |
| O | グリッパーを開く |
| C | グリッパーを閉じる |
| Space | 一時停止 / 再開 |
| Enter | リセット |
| Esc | 終了 |

## 既存Viewer

従来の手動Viewerも維持しています。

```bash
uv run mjpython scripts/run_manual.py
```

`run_manual.py`は関節選択型の操作です。キー割り当てはREADMEのManual Viewer表を参照してください。

## ビジュアル

- ロボットはオフホワイトの外装、ダークグレーの関節、ブルーのアクセントを持つ研究用アーム風の見た目です。
- 追加外装、ジョイントカバー、リンクカバー、アクセントリング、ケーブル風表示、ロゴプレートはvisual専用geomです。
- target、pick、place領域は半透明表示です。
- visual専用geomは`contype=0`、`conaffinity=0`、`density=0`で、物理衝突や質量に影響しないようにしています。

## スクリーンショット

スクリーンショットは今後 `docs/screenshots/` に配置してください。
