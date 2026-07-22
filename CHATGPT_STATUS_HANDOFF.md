# Physical AI Sandbox 現状共有メモ

Last updated: 2026-07-22

## Repository

- GitHub: https://github.com/asuka0611/physical-ai-sandbox
- Local path: `/Users/miyachiasuka/Documents/prog/Physical AI Sandbox`
- Branch: `feature/macos-application`
- Git status at handoff: clean, synced with `origin/feature/macos-application`

## 現在の目的

Physical AI Sandboxは、MuJoCo上のPanda風7軸ロボットでPick and Place / grasp+liftを扱う実験環境です。

現在はPhase 5.1-5.9相当のWorkspace UI/UX改善を進めています。優先事項は新しいAI機能よりも、Fusion 360 / Blender / Onshapeに近い「単一ウィンドウの実験Workspace」として使いやすくすることです。

## 完了済みPhase概要

- Phase 1: MuJoCo環境、7関節ロボット、グリッパー、cube、target、reward、record/replay、headless検証
- Phase 2: Dataset基盤、Episode loader、固定長Observation、8D Action検証、split、normalization、manifest、CLI
- Phase 3: NumPy MLP Behavior Cloning、train/evaluate CLI、checkpoint/history/report
- Phase 3.5: BC checkpointの環境内rollout評価、controller、安全停止、複数Episode評価、記録/replay
- Phase 3.6: 固定初期条件grasp+liftデモ30 Episode、Dataset再生成、BC再学習、rollout smoke評価
- Phase 4: PPO基盤、Actor/Critic、rollout buffer、GAE、PPO update、checkpoint/resume/evaluate/compare
- Phase 4.6: macOSローカルLauncher化。配布用bundleではなく、このMacのローカル開発環境を起動するLauncher
- Phase 5: Policy共通Interface、Random/Manual/BC/PPO、policy評価CLI、比較CLI、JSON/CSV/Markdown出力
- Phase 6/7: Sim2Real / Vision MVP Interfaceのみ。実機・実カメラ検証は未実施

## 現在のWorkspace構成

通常起動では外部の`MuJoCo Viewer`ウィンドウを開きません。

`Physical AI Sandbox Workspace`単一ウィンドウ内に、以下を表示します。

- Toolbar
- Project / Scene Tree
- 中央 3D Viewport
- Robot Inspector / Joint Controls
- Bottom tabs: Console / Metrics / Evaluation / Timeline / Problems

3D Viewportは`mujoco.viewer.launch_passive()`ではなく、simulation process側の`mujoco.Renderer`によるoffscreen renderingです。

描画フレームはPPMとしてIPCでTk Canvasへ送信され、中央Viewportに表示されます。

## macOS Launcher

生成物:

```text
dist/Physical AI Sandbox Launcher.app
```

Launcherは配布用アプリではありません。このMac上のローカル開発環境専用です。

ダブルクリック時に実行する処理の意図:

```bash
cd "/Users/miyachiasuka/Documents/prog/Physical AI Sandbox"
uv run python scripts/run_control_panel.py
```

重要:

- Terminalウィンドウは開かない
- Python/MuJoCo/依存関係は同梱しない
- `uv sync`済みのローカル環境が必要
- `uv run mjpython`が利用可能であることが必要
- 二重起動時は既存`run_control_panel.py`を検出し、新しいWorkspaceを増やさない

## 直近で実装したUI/UX改善

### Manual Test最終修正

- Manual Testでは1000 step到達によるepisode終了を禁止
- Manual Testでは1000 step到達によるsimulation resetを禁止
- Manual Testでは1000 step到達によるrobot/object初期化を禁止
- Manual TestではAI学習用データ記録、trajectory保存、dataset writer起動をUI側・simulation側の両方でブロック
- Manual Testの状態はユーザーがResetを押すまで維持
- Viewport overlayはManual Test中に以下を表示:

```text
Mode: Manual Test
Recording: OFF
Session Step: 4382
Elapsed: 00:02:18
```

### Camera

- 左ドラッグ: Orbit
- Shift + 左ドラッグ: Pan
- 中ドラッグ: Pan
- ホイール: Zoom
- ダブルクリック: selected jointへFocus、またはIsometricへ復帰
- Camera Reset
- Preset views: Front / Right / Top / Back / Left / Bottom / Isometric
- Camera state保存・復元
- Renderer再起動後のCamera state復元
- Workspace再起動後のCamera state復元

### Camera Gizmo

- Viewport右上に簡易Camera Gizmoを表示
- 中央クリックでIsometric
- X/Y/Zラベルクリックでプリセット視点へ切り替え

### Joint表示

- Viewport上にJ1-J7ラベルをCanvas overlayとして表示
- MuJoCo内のjoint label siteを2D投影して描画
- 選択中Jointは黄色表示
- Inspector行も強調
- Scene Tree、Viewport、Inspector、snapshot statusが同期
- Joint選択時にCamera Focus

注意: クリック判定はoverlay labelの2D hit targetであり、完全な3D mesh pickingではありません。

### Layout

- Tk `PanedWindow`で左右・上下パネルをドラッグリサイズ可能
- Viewport MaximizeでProject / Inspector / Bottomを非表示
- Zen ModeでViewport中心の表示
- Layout Reset追加
- Layout / hidden panels / active tab / selected joint / mode / overlay / camera stateを保存
- 保存先: `~/Library/Application Support/Physical AI Sandbox/workspace_state.json`

### Mode

- Manual TestとAI Recordingを分離
- Manual Testでは記録開始をブロック
- AI RecordingではREC / Stop RECを使用
- recording中はViewport overlayに赤いREC表示

### Overlay

Viewport overlayに表示:

- Episode
- Step
- Reward
- FPS
- Policy
- Mode
- Recording
- Simulation Hz
- Selected Joint
- Input context

### Performance / Stability

- idle時にRendererが同じframeを30FPSで送り続けないよう調整
- paused時のsnapshot送信を低頻度化
- simulation running時は高頻度更新へ戻す
- Viewport最大化時にMuJoCo offscreen framebuffer上限を超えて落ちる問題を修正

## 重要ファイル

- UI本体: `src/physical_ai_sandbox/ui/control_panel.py`
- Simulation / Renderer process: `src/physical_ai_sandbox/ui/simulation_process.py`
- UI command/snapshot types: `src/physical_ai_sandbox/ui/control_types.py`
- Input focus管理: `src/physical_ai_sandbox/ui/input_manager.py`
- Launcher source: `packaging/macos/LocalLauncher.swift`
- Launcher build: `scripts/build_macos_app.sh`
- Launcher clean: `scripts/clean_macos_build.sh`
- UI guide: `docs/ui_workspace.md`
- Screenshot: `docs/screenshots/workspace_ui_phase_2026-07-22.png`

## 最新コミット

```text
2a84c9a fix: clamp viewport renderer resize to framebuffer
140c136 docs: update workspace ui phase status
6e4d6d6 perf: throttle paused workspace snapshots
641548b perf: reduce idle workspace rendering load
f130670 feat: persist workspace layout state
e7e0ada feat: add interactive viewport camera controls
27a435b fix: launch workspace from macOS launcher process
d924e24 fix: embed MuJoCo viewport in workspace
```

## 検証結果

最終確認済み:

```bash
uv sync
uv run ruff check .
uv run pytest
uv run python scripts/validate_config.py
uv run python scripts/run_headless.py --steps 1000
bash scripts/clean_macos_build.sh
bash scripts/build_macos_app.sh
codesign --verify --deep --strict "dist/Physical AI Sandbox Launcher.app"
```

結果:

- `uv sync`: passed
- `ruff`: passed
- `pytest`: 104 passed
- config validation: passed
- headless 1000 steps: passed
- macOS Launcher build: passed
- codesign strict verification: passed

Manual / visual checks:

- LauncherからWorkspace起動: OK
- `run_control_panel.py` / simulation processは1系統のみ: OK
- 二重起動防止: OK
- 外部MuJoCo Viewerなし: OK
- 単一Workspace内の3D Viewport表示: OK
- Robot/table/cube/target表示: OK
- Camera Gizmo表示: OK
- J1-J7 overlay表示: OK
- 終了後残留プロセスなし: OK

## 既知の未完了・注意点

- 実マウス操作のOrbit/Pan/Zoomはコード経路と画面表示まで確認済み。ただし長時間の手動ドラッグ検証は未完。
- Replay TimelineのScrubber / Frame Jump / Speed変更は未実装。
- Joint selectionは2D overlay label hit target方式。完全な3D mesh pickingではない。
- 長時間memory leak検証は未実施。短時間RSS/CPU sampleのみ。
- Phase 6/7はMVP interfaceのみ。実機ロボット、実カメラ、Sim2Real性能は未検証。
- BC/PPOの評価結果は固定初期条件・grasp+lift smoke範囲。汎化性能や完全Pick and Place性能は断定しない。

## 次にやると良いこと

1. ユーザー操作でCamera Orbit/Pan/Zoomを実際に数分試す。
2. Viewport Maximize / Zen Mode / Layout Reset後にWorkspace再起動し、layout restoreを確認する。
3. AI Recording modeでREC開始・停止し、Manual Testでは保存されないことを実ログで確認する。
4. Timeline Replay UIを実装する。
5. Joint selectionを将来的にMuJoCo depth/ID buffer等で3D pickingへ拡張する。
6. 10分以上の連続起動でCPU/RSS推移を確認する。
