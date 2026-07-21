from __future__ import annotations

import argparse
import json
from pathlib import Path

from physical_ai_sandbox.evaluation.bc_rollout import BCRolloutEvaluator, RolloutConfig
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a Behavior Cloning checkpoint in closed-loop headless rollout.",
    )
    parser.add_argument("model_dir")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default=None)
    parser.add_argument("--log-root", default="logs/bc_rollouts")
    parser.add_argument("--no-record", action="store_true")
    parser.add_argument("--no-replay", action="store_true")
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    output = Path(args.output) if args.output else model_dir / "rollout_report.json"
    rollout_config = RolloutConfig(
        episodes=args.episodes,
        max_steps=args.max_steps,
        seed=args.seed,
        record=not args.no_record,
        replay=not args.no_replay,
    )
    report = BCRolloutEvaluator(
        model_dir,
        config_path=args.config,
        log_root=args.log_root,
        rollout_config=rollout_config,
    ).evaluate(report_path=output)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
