from __future__ import annotations

import argparse

from physical_ai_sandbox.learning.bc.trainer import BehaviorCloningTrainer, TrainingConfig


def _hidden_sizes(value: str) -> tuple[int, ...]:
    if not value:
        return ()
    return tuple(int(part) for part in value.split(","))


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a Phase 3 Behavior Cloning policy.")
    parser.add_argument("--dataset", default="datasets/pick_place_v1")
    parser.add_argument("--output", default="models/bc_pick_place_v1")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hidden-sizes", default="64,64")
    args = parser.parse_args()
    config = TrainingConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        seed=args.seed,
        hidden_sizes=_hidden_sizes(args.hidden_sizes),
    )
    result = BehaviorCloningTrainer(config).train_from_dataset(args.dataset, args.output)
    print(
        {
            "output_dir": str(result.output_dir),
            "checkpoint": str(result.checkpoint_path),
            "epochs": len(result.history),
            "final_train_mse": result.history[-1]["train_mse"],
            "final_validation_mse": result.history[-1]["validation_mse"],
            "warnings": result.evaluation["warnings"],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
