from __future__ import annotations

import argparse
import json
from pathlib import Path

from physical_ai_sandbox.evaluation.bc_rollout import BCRolloutEvaluator, RolloutConfig
from physical_ai_sandbox.learning.ppo.trainer import PPOTrainer, PPOTrainingConfig


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare BC-only, random PPO, and BC-initialized PPO smoke runs.",
    )
    parser.add_argument("--output", default="models/ppo_phase4_smoke_compare")
    parser.add_argument("--dataset", default="datasets/grasp_lift_v1")
    parser.add_argument("--bc-model", default="models/bc_grasp_lift_v1")
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=120)
    parser.add_argument("--total-steps", type=int, default=128)
    parser.add_argument("--rollout-steps", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    bc_report = BCRolloutEvaluator(
        args.bc_model,
        log_root=output / "bc_only_rollouts",
        rollout_config=RolloutConfig(
            episodes=args.episodes,
            max_steps=args.max_steps,
            seed=args.seed,
            record=True,
            replay=True,
        ),
    ).evaluate(report_path=output / "bc_only_report.json")
    reports = {"bc_only": bc_report}
    for init in ("random", "bc"):
        trainer = PPOTrainer(
            PPOTrainingConfig(
                total_steps=args.total_steps,
                rollout_steps=args.rollout_steps,
                max_episode_steps=args.max_steps,
                seed=args.seed,
                init=init,
            ),
        )
        result = trainer.train(
            output / f"ppo_{init}",
            dataset_dir=args.dataset,
            bc_model_dir=args.bc_model if init == "bc" else None,
        )
        reports[f"ppo_{init}"] = result.evaluation
    summary = {
        "comparison": {name: report["metrics"] for name, report in reports.items()},
        "warnings": [
            "BC-only fixed-condition grasp_lift_success_rate is the baseline.",
            "Short PPO smoke training can degrade performance; compare only under "
            "the recorded steps, seed, episodes, and initialization.",
        ],
        "settings": {
            "dataset": args.dataset,
            "bc_model": args.bc_model,
            "episodes": args.episodes,
            "max_steps": args.max_steps,
            "total_steps": args.total_steps,
            "rollout_steps": args.rollout_steps,
            "seed": args.seed,
        },
    }
    (output / "comparison_report.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
