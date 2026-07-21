# Phase 3.5 Completion Status

Last verified: 2026-07-21

## Implemented

- `BehaviorCloningController` for Phase 3 checkpoints.
- Checkpoint loading from model directory or explicit `policy_checkpoint.npz`.
- Observation encoding with the same Phase 2 feature order used at training time.
- Observation normalization using checkpoint `observation_mean` and `observation_safe_std`.
- Fixed 8D Action inference through the NumPy MLP policy.
- Controller-side Action clipping to `[-1.0, 1.0]`.
- NaN/Inf safe-stop behavior that returns a zero Action and unsafe reason.
- Headless multi-Episode rollout evaluator.
- Rollout metrics for success rate, total reward, grasp rate, lift rate, goal-reaching rate, replay count, and failure reasons.
- Rollout Episode recording to `logs/bc_rollouts` by the CLI.
- Replay confirmation for recorded rollout Episodes.
- Seed recording and reproducibility test coverage.
- CLI script: `scripts/evaluate_bc_rollout.py`.

## Command

```bash
uv run python scripts/evaluate_bc_rollout.py \
  models/bc_pick_place_v1 \
  --episodes 3 \
  --max-steps 200 \
  --seed 42
```

## Rollout Result

Output: `models/bc_pick_place_v1/rollout_report.json`

Recorded Episodes: `logs/bc_rollouts`

- Episodes: 3
- Steps: 200 per Episode
- Success count: 0
- Success rate: 0.0
- Average total reward: -55.6917177980557
- Grasp rate: 0.0
- Lift rate: 0.0
- Goal reached rate: 0.0
- Replay count: 3
- Replay success count: 0
- Failure reasons: `max steps reached`: 3
- Unsafe controller outputs: none observed

## Important Interpretation

Phase 3.5 confirms that the BC checkpoint can be loaded, normalized with
training statistics, clipped, safety-checked, and executed through the
Environment API without crashing. The current dataset has only 5 valid Episodes
and the test split has only 5 samples / 1 Episode, so the rollout result must
not be treated as BC control performance, Pick-and-Place success capability, or
generalization evidence.

## Verification Commands

- `uv sync`: passed
- `uv run ruff check .`: passed
- `uv run pytest`: passed, 36 tests
- `uv run python scripts/validate_config.py`: passed
- `uv run python scripts/run_headless.py --steps 1000`: passed
- `uv run python scripts/validate_dataset.py datasets/pick_place_v1`: passed
- `uv run python scripts/evaluate_behavior_cloning.py models/bc_pick_place_v1 --dataset datasets/pick_place_v1`: passed
- `uv run python scripts/evaluate_bc_rollout.py models/bc_pick_place_v1 --episodes 3 --max-steps 200 --seed 42`: passed

## Not Implemented In Phase 3.5

- PPO/SAC
- DAgger
- Online policy improvement
- Contact-rich grasp learning
- Camera/image policy
- Real-robot or drone connection

## Phase 3.6 Follow-up

Phase 3.6 adds a separate fixed-condition grasp+lift collection, Dataset, and
BC model. It does not replace the Phase 3.5 safety evaluator; the evaluator now
also reports `grasp_lift_success_rate` for simplified-task rollouts.
