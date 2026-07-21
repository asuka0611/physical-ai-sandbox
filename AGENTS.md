# Agent Rules

Every implementation pass should:

1. Read `PROJECT_CONTEXT.md`.
2. Read `ARCHITECTURE.md`.
3. Read `AGENTS.md`.
4. Check existing code before editing.
5. Keep changes scoped to the requested phase.
6. Run `uv sync`.
7. Run `uv run ruff check .`.
8. Run `uv run pytest`.
9. Run `uv run python scripts/validate_config.py`.
10. Update README, CHANGELOG, known issues, and completion status when behavior changes.

Do not:

- Change Action semantics casually.
- Remove Observation fields.
- Make viewer access required for core environment logic.
- Add Phase 2+ AI training code during Phase 1.
- Connect to real robots or deploy to hardware without explicit user approval.
