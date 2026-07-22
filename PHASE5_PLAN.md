# Phase 5 Plan: Policy Evaluation Workbench

## Status

Phase 5 headless policy evaluation has started. The shared Policy interface, headless evaluation runner, comparison CLI, and JSON/CSV/Markdown outputs are implemented. UI evaluation controls and Viewer trajectory replay remain planned work.

## Goal

Turn Physical AI Sandbox into an experiment environment that can compare and evaluate trained policies under shared environment, seed, and metric contracts.

## Scope

- Shared Policy interface.
- Manual, Random, Behavior Cloning, and PPO policy adapters.
- Multi-episode evaluation runner.
- JSON and CSV result output.
- Same-seed policy comparison.
- Replay-ready action trajectory metadata.
- Minimal UI integration after the runner is stable.

## Implemented Files

- `src/physical_ai_sandbox/policies/base.py`
- `src/physical_ai_sandbox/policies/manual.py`
- `src/physical_ai_sandbox/policies/random.py`
- `src/physical_ai_sandbox/policies/bc.py`
- `src/physical_ai_sandbox/policies/ppo.py`
- `src/physical_ai_sandbox/policies/factory.py`
- `src/physical_ai_sandbox/evaluation/policy_runner.py`
- `src/physical_ai_sandbox/evaluation/policy_metrics.py`
- `src/physical_ai_sandbox/evaluation/policy_compare.py`
- `scripts/evaluate_policy.py`
- `scripts/compare_policies.py`
- `docs/policy_evaluation.md`
- `PHASE5_COMPLETION_STATUS.md`

Pending UI/replay files should be added only after the CLI runner remains stable.

## Policy Interface

```python
class Policy(Protocol):
    def reset(self, *, seed: int | None = None) -> None: ...
    def act(self, observation: Observation, *, deterministic: bool = True) -> PolicyAction: ...
    def close(self) -> None: ...
    def metadata(self) -> dict[str, object]: ...
```

`PolicyAction` should contain:

- `action: np.ndarray`
- `is_safe: bool`
- `unsafe_reason: str | None`

Adapters should reuse existing controller/model code:

- `ManualPolicy`: thin wrapper around current manual action contract; excluded from automated batch comparison by default.
- `RandomPolicy`: seeded `np.random.Generator`, fixed 8D action clipping.
- `BehaviorCloningPolicy`: wrap `BehaviorCloningController` and reuse training-time normalization.
- `PPOPolicy`: wrap existing PPO checkpoint actor/critic loading and deterministic/stochastic action path.

## Evaluation Runner

CLI shape:

```bash
uv run python scripts/evaluate_policy.py   --policy bc   --model models/bc_grasp_lift_v1   --episodes 20   --seed 42   --headless   --deterministic   --max-steps 200   --output logs/evaluation/bc_seed42.json
```

Inputs:

- policy name
- optional model path
- episodes
- seed
- headless/viewer
- deterministic flag
- max steps
- output path
- optional trajectory recording

## Metrics

Record per episode:

- episode number
- seed
- success
- grasp_lift_success
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
- episode log path or replay trajectory path

Success should reuse the existing Phase 3.6 grasp+lift condition. Do not redefine task success in the runner.

## Policy Comparison

CLI shape:

```bash
uv run python scripts/compare_policies.py   --policies random,bc,ppo   --bc-model models/bc_grasp_lift_v1   --ppo-model models/ppo_smoke_v1   --episodes 10   --seeds 42,43,44   --output-dir logs/evaluation/compare_seed42
```

Outputs:

- JSON detailed report
- CSV episode table
- Markdown summary

Summary columns:

- policy
- success rate
- mean reward
- reward standard deviation
- mean episode length
- mean completion time
- failure reason counts

## UI Integration

Add controls only after the CLI runner is stable:

- policy selector
- model path selector
- seed input
- episode count input
- start evaluation
- stop evaluation
- progress
- latest result
- open results folder

Evaluation must run off the Tk UI thread. The Phase 4.6 UI/simulation IPC should not be overloaded with long-running evaluation until the CLI runner is proven stable.

## Replay Plan

Minimum replay-ready output:

- initial seed
- initial config path
- action trajectory
- policy metadata
- episode result path

Prefer reusing `EpisodeRecorder` and `scripts/replay_episode.py` rather than creating a new replay format.

## Tests

- Policy protocol compatibility.
- RandomPolicy action shape, clipping, and seed reproducibility.
- BC checkpoint load and invalid path failure.
- PPO checkpoint load and invalid path failure.
- deterministic action behavior.
- evaluation metrics extraction.
- grasp+lift success判定 reuse.
- JSON save/load.
- CSV save/load.
- same-seed reproducibility.
- policy comparison aggregation.
- evaluation interruption.
- UI evaluation message format.
- existing headless, BC, and PPO regression.

## Completion Criteria

Phase 5 should be marked complete only after:

- BC and PPO run through the shared interface.
- One command evaluates multiple episodes.
- JSON or CSV results are saved.
- Same-seed comparison works.
- Automated tests pass.
- Existing headless execution still passes.
- At least one BC real evaluation completes.
- PPO real evaluation completes if a PPO checkpoint exists.
- Results and limitations are documented.

If no trained PPO checkpoint exists, implement PPO loading/inference interface but mark Phase 5 as partial, not complete.
