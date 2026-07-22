# Policy Evaluation

Phase 5 adds a shared policy evaluation layer for fixed-initial-condition grasp+lift experiments.

## Scope

Implemented in this pass:

- Shared `Policy` interface with `reset()`, `act()`, `close()`, and `metadata()`.
- `RandomPolicy`, `ManualPolicy`, `BehaviorCloningPolicy`, and `PPOPolicy` adapters.
- Headless multi-episode evaluation through `scripts/evaluate_policy.py`.
- Same-seed policy comparison through `scripts/compare_policies.py`.
- JSON, CSV, and Markdown comparison outputs.
- Action trajectory storage in evaluation JSON for replay-oriented follow-up work.

Not implemented yet:

- Tk UI controls for starting/stopping policy evaluation.
- Viewer replay from saved trajectories.
- Long-running or randomized-condition benchmark claims.

## Evaluate One Policy

```bash
uv run python scripts/evaluate_policy.py \
  --policy bc \
  --model models/bc_grasp_lift_v1 \
  --episodes 20 \
  --seed 42 \
  --headless \
  --max-steps 200 \
  --output logs/evaluation/bc_seed42.json
```

The command also writes a CSV next to the JSON unless `--csv-output` is specified.

Supported policies:

- `random`
- `manual` (contract placeholder; automated comparison excludes manual by default)
- `bc` with `--model`
- `ppo` with `--model`

## Compare Policies

```bash
uv run python scripts/compare_policies.py \
  --policies random,bc,ppo \
  --bc-model models/bc_grasp_lift_v1 \
  --ppo-model models/ppo_grasp_lift_bc_smoke \
  --episodes 10 \
  --seed 42 \
  --max-steps 200 \
  --output-dir logs/evaluation/compare_seed42
```

Outputs:

- `comparison_report.json`
- `comparison_summary.csv`
- `comparison_summary.md`
- per-policy JSON and CSV reports

## Metrics

Each episode records:

- episode number
- seed
- success / grasp-lift success
- total reward
- episode length
- completion time
- final object height
- grasp achieved
- lift achieved
- termination reason
- policy name
- model path
- timestamp
- action trajectory

The success flag currently reuses the Phase 3.6 fixed-condition grasp+lift criterion. It is not a full Pick-and-Place success claim.

## Verification Snapshot

Verified on 2026-07-22:

- BC shared-interface evaluation: `models/bc_grasp_lift_v1`, 1 Episode, seed 42, headless, passed.
- PPO shared-interface evaluation: `models/ppo_grasp_lift_bc_smoke`, 1 Episode, seed 42, headless, passed.
- Random/BC/PPO comparison: 1 Episode each, seed 42, generated JSON/CSV/Markdown.

These are smoke checks under fixed initial conditions. Do not interpret them as generalized model performance.
