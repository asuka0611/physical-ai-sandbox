# Phase 1 Completion Status

Last verified: 2026-07-21

## Verification Commands

- `uv sync`: passed in target project folder
- `uv run ruff check .`: passed
- `uv run pytest`: passed, 11 tests
- `uv run python scripts/validate_config.py`: passed
- `uv run python scripts/run_headless.py --steps 1000`: passed
- `uv run python scripts/run_headless.py --steps 5 --record`: passed
- `uv run python scripts/replay_episode.py logs/episodes/episode_20260721_005935_117977`: passed
- `uv run python scripts/run_pick_place_demo.py --record`: passed; grasped, lifted, placed, and success=True
- `uv run python scripts/run_pick_place_demo.py --viewer --record --hold-seconds 1`: passed; Viewer child process exited with code 0 and no process remained
- `uv run pytest tests/test_manual_controller.py`: passed; 1-7 joint selection, previous/next selection, move action, and gripper toggle

## Required Features

- [x] MuJoCo scene can instantiate a Panda-style 7-axis arm.
- [x] Table, cube, target region, floor, box obstacle, and cylinder obstacle are in the model.
- [x] Seven arm joints accept clipped delta actions.
- [x] Gripper open/close command is represented in the fixed 8D action.
- [x] Manual key handling covers direct selection of all 7 joints and gripper toggle.
- [x] Cube grasp state is implemented with deterministic near-gripper attachment.
- [x] Cube can be lifted while grasped by the deterministic attachment rule.
- [x] Cube can be placed/released over the target region.
- [x] Success evaluation tracks target position, table support, speed threshold, and stable time, and matches the scripted visible target placement.
- [x] Failure evaluation tracks time limit, dropped cube, and non-finite state.
- [x] Reset works and is covered by five consecutive reset test.
- [x] JSONL operation logs are saved per episode.
- [x] Episode summaries are saved.
- [x] Replay applies saved action sequences.
- [x] YAML `box` obstacles are supported and tested.
- [x] YAML `cylinder` obstacles are supported and tested.
- [x] JSON Schema validates configuration.
- [x] Viewer-free reset, step, reward, success/failure, logging, and tests run.
- [x] 1000 physical steps run without NaN in the smoke command.

## Quality Conditions

- [x] `uv run pytest` passes.
- [x] `uv run ruff check .` passes.
- [x] README documents setup, validation, manual run, headless run, replay, Action, and Observation.
- [x] CHANGELOG updated.
- [x] Error messages are explicit for invalid config, invalid action shape, NaN/Inf actions, and missing observation fields.
- [x] Action range is safely clipped.
- [x] Observation required fields are validated.
- [x] Log required fields are covered by tests.

## GUI Validation Notes

- Viewer final-state startup was verified through `scripts/run_pick_place_demo.py --viewer`; the Viewer child process exited cleanly with no remaining `mjpython` process.
- Controller-level key handling was verified by tests. Direct OS-level hand-keyed control could not be automated from the Codex command runner; run `uv run mjpython scripts/run_manual.py` in Terminal for human operation.

## Limitations

See `KNOWN_ISSUES.md`. The largest Phase 1 limitation is that grasping is deterministic rather than contact-rich physics.

## Phase 3.5 Revalidation Note

Phase 3.5 reuses the Phase 1 Environment API without changing the manual-control
contracts. The standard config/headless validations were rerun after the BC
rollout additions.
