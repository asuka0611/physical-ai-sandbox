# UI Guide JA

## 起動

日本語Workspaceと埋め込み3D Viewportを起動します。

```bash
uv run python scripts/run_control_panel.py
```

英語表示で起動する場合:

```bash
uv run python scripts/run_control_panel.py --language en
```

Workspace本体は通常Python/Tkinterで起動します。MuJoCo simulationとoffscreen renderingは内部で別の`mjpython`プロセスとして起動し、3Dフレームを中央Viewportへ表示します。

## 操作パネル

- 実行状態、エピソード、ステップ、報酬、把持、持ち上げ、成功、記録状態を表示します。
- 言語メニューで日本語と英語を切り替えられます。
- `Start`、`Pause/Resume`、`Reset`、`Quit`で実行状態を制御します。
- Modeで`Manual Test`と`AI Recording`を切り替えます。Manual TestではEpisodeを保存しません。
- `REC`、`Stop REC`でAI Recording中のEpisode記録を開始・停止します。
- `Open Gripper`、`Close Gripper`でグリッパーを開閉します。
- XYZ操作ボタンは固定8次元Actionに変換されます。Observation、Action、Dataset仕様は変更していません。
- J1からJ7の`+` / `-`ボタンで7関節を直接操作できます。
- 操作量スライダーで1回の操作量を調整できます。

## Viewport

- 左ドラッグ: Orbit
- Shift + 左ドラッグ、または中ドラッグ: Pan
- ホイール: Zoom
- ダブルクリック: 選択JointへFocus、またはIsometricへ復帰
- `Camera Reset`: 初期カメラへ戻す
- `Front`、`Right`、`Top`、`Back`、`Left`、`Bottom`、`Isometric`: プリセット視点
- 右上のCamera Gizmo: 中央クリックでIsometric、X/Y/Zラベルでプリセット視点へ切り替え

## Joint表示

- Viewport上にJ1-J7ラベルを表示します。
- Scene Tree、Viewportラベル、Robot Inspectorの選択は同期します。
- 選択中のJointは黄色で表示され、Inspector行が強調され、カメラがそのJointへFocusします。

## Layout

- Project、Viewport、Inspector、Bottomの境界線をドラッグしてサイズ変更できます。
- `Viewport最大化`はProject、Inspector、Bottomを隠します。
- `Zen Mode`はViewportだけに集中する表示です。
- `Layout Reset`はパネル表示を初期状態へ戻します。
- Camera、Layout、Hidden Panels、Selected Joint、Active Tab、Mode、Overlay表示はWorkspace終了時に保存され、次回起動時に復元されます。

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
| Esc | 入力解除 |

## 既存Viewer

従来の手動MuJoCo Viewerも別CLIとして維持しています。WorkspaceのControlPanel経路では別Viewerウィンドウを開きません。

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
