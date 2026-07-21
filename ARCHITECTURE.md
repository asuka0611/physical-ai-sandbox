# Architecture

## Boundaries

- `physical_ai_sandbox.envs`: Environment API: `reset`, `step`, `render`, `close`.
- `physical_ai_sandbox.controllers`: Manual and replay action sources.
- `physical_ai_sandbox.recording`: Episode persistence.
- `physical_ai_sandbox.evaluation`: Reward, success, and failure checks.
- `physical_ai_sandbox.scene`: YAML config loading, schema validation, and MJCF generation.

## Core API

The environment returns:

```python
observation, reward, terminated, truncated, info
```

`observation` and `action` semantics are stable contracts. Future phases can add
fields, but must not remove or change existing fields without a migration.

## Safety

Actions are clipped to `[-1.0, 1.0]`. Joint targets are then clipped to MuJoCo
joint ranges. Headless operation is first-class so future RL training does not
depend on a viewer.
