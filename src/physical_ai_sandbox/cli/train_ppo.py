from __future__ import annotations

import argparse
import json

from physical_ai_sandbox.learning.ppo.trainer import PPOTrainer, PPOTrainingConfig


def _hidden_sizes(value: str) -> tuple[int, ...]:
    if not value:
        return ()
    return tuple(int(part) for part in value.split(","))


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a Phase 4 NumPy PPO smoke policy.")
    parser.add_argument("--output", default="models/ppo_grasp_lift_bc_smoke")
    parser.add_argument("--dataset", default="datasets/grasp_lift_v1")
    parser.add_argument("--bc-model", default="models/bc_grasp_lift_v1")
    parser.add_argument("--config", default=None)
    parser.add_argument("--init", choices=("bc", "random"), default="bc")
    parser.add_argument("--total-steps", type=int, default=256)
    parser.add_argument("--rollout-steps", type=int, default=64)
    parser.add_argument("--max-episode-steps", type=int, default=120)
    parser.add_argument("--update-epochs", type=int, default=3)
    parser.add_argument("--minibatch-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hidden-sizes", default="64,64")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    config = PPOTrainingConfig(
        total_steps=args.total_steps,
        rollout_steps=args.rollout_steps,
        max_episode_steps=args.max_episode_steps,
        update_epochs=args.update_epochs,
        minibatch_size=args.minibatch_size,
        seed=args.seed,
        init=args.init,
        hidden_sizes=_hidden_sizes(args.hidden_sizes),
    )
    trainer = PPOTrainer(config)
    kwargs = {} if args.config is None else {"config_path": args.config}
    result = trainer.train(
        args.output,
        dataset_dir=args.dataset,
        bc_model_dir=args.bc_model if args.init == "bc" else None,
        resume=args.resume,
        **kwargs,
    )
    print(
        json.dumps(
            {
                "output_dir": str(result.output_dir),
                "checkpoint": str(result.checkpoint_path),
                "history_length": len(result.history),
                "evaluation_metrics": result.evaluation["metrics"],
            },
            indent=2,
            sort_keys=True,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
