from __future__ import annotations

import argparse
import json

from physical_ai_sandbox.learning.ppo.evaluation import evaluate_ppo
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a Phase 4 PPO checkpoint.")
    parser.add_argument("model_dir")
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--max-steps", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--log-root", default="logs/ppo_rollouts")
    parser.add_argument("--output", default=None)
    parser.add_argument("--no-record", action="store_true")
    args = parser.parse_args()
    report = evaluate_ppo(
        args.model_dir,
        episodes=args.episodes,
        max_steps=args.max_steps,
        seed=args.seed,
        config_path=args.config,
        record=not args.no_record,
        log_root=args.log_root,
        output=args.output,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
