from __future__ import annotations

import argparse
import json
from pathlib import Path

from physical_ai_sandbox.evaluation.policy_runner import PolicyEvaluationConfig, evaluate_policy
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH
from physical_ai_sandbox.policies.factory import create_policy


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a policy through the shared Phase 5 interface.",
    )
    parser.add_argument("--policy", required=True, choices=["random", "manual", "bc", "ppo"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--output", default="logs/policy_evaluation/report.json")
    parser.add_argument("--csv-output", default=None)
    parser.add_argument("--log-root", default="logs/policy_evaluation")
    parser.add_argument("--headless", dest="headless", action="store_true", default=True)
    parser.add_argument("--viewer", dest="headless", action="store_false")
    parser.add_argument("--deterministic", dest="deterministic", action="store_true", default=True)
    parser.add_argument("--stochastic", dest="deterministic", action="store_false")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--no-trajectory", action="store_true")
    args = parser.parse_args()
    policy = create_policy(args.policy, model_path=args.model, seed=args.seed)
    csv_output = args.csv_output
    if csv_output is None and args.output:
        output_path = Path(args.output)
        csv_output = output_path.with_suffix(".csv")
    report = evaluate_policy(
        policy,
        config=PolicyEvaluationConfig(
            episodes=args.episodes,
            max_steps=args.max_steps,
            seed=args.seed,
            headless=args.headless,
            deterministic=args.deterministic,
            record=args.record,
            config_path=args.config,
            log_root=args.log_root,
            save_trajectory=not args.no_trajectory,
        ),
        model_path=args.model,
        output=args.output,
        csv_output=csv_output,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
