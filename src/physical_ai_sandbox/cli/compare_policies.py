from __future__ import annotations

import argparse
import json
from pathlib import Path

from physical_ai_sandbox.evaluation.policy_compare import compare_policies


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare policies under the shared Phase 5 evaluator.",
    )
    parser.add_argument("--policies", default="random,bc,ppo")
    parser.add_argument("--bc-model", default=None)
    parser.add_argument("--ppo-model", default=None)
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--output-dir", default="logs/policy_comparison")
    parser.add_argument("--deterministic", dest="deterministic", action="store_true", default=True)
    parser.add_argument("--stochastic", dest="deterministic", action="store_false")
    args = parser.parse_args()
    policies = [item.strip() for item in args.policies.split(",") if item.strip()]
    model_paths: dict[str, str | Path] = {}
    if args.bc_model is not None:
        model_paths["bc"] = args.bc_model
    if args.ppo_model is not None:
        model_paths["ppo"] = args.ppo_model
    report = compare_policies(
        policies,
        model_paths=model_paths,
        episodes=args.episodes,
        seed=args.seed,
        max_steps=args.max_steps,
        deterministic=args.deterministic,
        output_dir=args.output_dir,
    )
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
