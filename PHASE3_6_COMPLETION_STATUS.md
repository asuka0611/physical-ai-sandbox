# Phase 3.6 Completion Status

Last verified: 2026-07-21

## Implemented

- Fixed-initial-condition grasp+lift demonstration collector.
- Simplified task: immediate gripper close, deterministic lift motion, no release/place requirement.
- `collect_grasp_lift_demos.py` CLI.
- `physical-ai-collect-grasp-lift` entrypoint.
- Collection report with Episode count, fixed-condition flag, grasp rate, lift rate, task success rate, seed, and interpretation warning.
- Separate logs under `logs/grasp_lift_demos`.
- Separate Dataset: `datasets/grasp_lift_v1`.
- Separate BC model: `models/bc_grasp_lift_v1`.
- Closed-loop rollout report now includes `grasp_lift_success_rate`.
- Automated test for fixed-condition grasp+lift collection and Episode loadability.

## Data Collection

Command:

```bash
uv run python scripts/collect_grasp_lift_demos.py \
  --episodes 30 \
  --output logs/grasp_lift_demos \
  --seed 42 \
  --overwrite
```

Result:

- Episodes: 30
- Fixed initial condition: true
- Task: `fixed_initial_grasp_lift`
- Task success count: 30
- Grasp count: 30
- Lift count: 30
- Broken Episodes: 0

## Dataset

Command:

```bash
uv run python scripts/build_dataset.py \
  --episodes logs/grasp_lift_demos \
  --output datasets/grasp_lift_v1 \
  --name grasp_lift \
  --version v1 \
  --seed 42
```

Result:

- Dataset: `datasets/grasp_lift_v1`
- Episodes: 30
- Samples: 1800
- Train: 1440 samples / 24 Episodes
- Validation: 180 samples / 3 Episodes
- Test: 180 samples / 3 Episodes
- Dataset success rate from Episode summaries: 1.0

## Training

Command:

```bash
uv run python scripts/train_behavior_cloning.py \
  --dataset datasets/grasp_lift_v1 \
  --output models/bc_grasp_lift_v1 \
  --epochs 120 \
  --batch-size 64 \
  --learning-rate 0.01 \
  --seed 42
```

Result:

- Model: `models/bc_grasp_lift_v1`
- Final train MSE: 0.0009418404139435513
- Final validation MSE: 0.0009418404139435513
- Test MSE after checkpoint reload: 0.0009418404139435513
- Test samples: 180 / 3 Episodes

## Rollout Evaluation

Command:

```bash
uv run python scripts/evaluate_bc_rollout.py \
  models/bc_grasp_lift_v1 \
  --episodes 10 \
  --max-steps 120 \
  --seed 42 \
  --log-root logs/bc_grasp_lift_rollouts
```

Result:

- Rollout Episodes: 10
- Average total reward: 58.223261526181986
- Grasp rate: 1.0
- Lift rate: 1.0
- Grasp+lift success rate: 1.0
- Goal reached rate: 1.0 under the current target-radius geometry
- Pick-and-Place success rate: 0.0
- Replay count: 10
- Unsafe controller outputs: none observed
- Failure reasons: `max steps reached`: 10

## Interpretation

Phase 3.6 shows that targeted fixed-condition grasp+lift data improves the
closed-loop grasp/lift behavior of the BC checkpoint under the same simplified
conditions. It does not prove full Pick-and-Place performance, release/place
behavior, robustness, randomized initial-state performance, obstacle handling,
or generalization.

## Verification Commands

- `uv sync`: passed
- `uv run ruff check .`: passed
- `uv run pytest`: passed, 37 tests
- `uv run python scripts/validate_config.py`: passed
- `uv run python scripts/run_headless.py --steps 1000`: passed
- `uv run python scripts/collect_grasp_lift_demos.py --episodes 30 --output logs/grasp_lift_demos --seed 42 --overwrite`: passed
- `uv run python scripts/build_dataset.py --episodes logs/grasp_lift_demos --output datasets/grasp_lift_v1 --name grasp_lift --version v1 --seed 42`: passed
- `uv run python scripts/validate_dataset.py datasets/grasp_lift_v1`: passed
- `uv run python scripts/inspect_dataset.py datasets/grasp_lift_v1`: passed
- `uv run python scripts/train_behavior_cloning.py --dataset datasets/grasp_lift_v1 --output models/bc_grasp_lift_v1 --epochs 120 --batch-size 64 --learning-rate 0.01 --seed 42`: passed
- `uv run python scripts/evaluate_behavior_cloning.py models/bc_grasp_lift_v1 --dataset datasets/grasp_lift_v1`: passed
- `uv run python scripts/evaluate_bc_rollout.py models/bc_grasp_lift_v1 --episodes 10 --max-steps 120 --seed 42 --log-root logs/bc_grasp_lift_rollouts`: passed

## Not Implemented In Phase 3.6

- Full Pick-and-Place BC success
- Release/place learning
- Randomized initial conditions
- DAgger
- PPO/SAC
- Image observations
- Real-robot or drone connection
