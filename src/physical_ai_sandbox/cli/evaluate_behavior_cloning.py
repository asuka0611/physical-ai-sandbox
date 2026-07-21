from __future__ import annotations

import argparse
import json
from pathlib import Path

from physical_ai_sandbox.learning.bc.dataset import (
    load_bc_dataset,
    normalize_observations,
    observation_normalizer,
)
from physical_ai_sandbox.learning.bc.evaluation import evaluate_policy
from physical_ai_sandbox.learning.bc.policy import MLPPolicy


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a Phase 3 Behavior Cloning policy.")
    parser.add_argument("model_dir")
    parser.add_argument("--dataset", default="datasets/pick_place_v1")
    args = parser.parse_args()
    model_dir = Path(args.model_dir)
    policy, metadata = MLPPolicy.load(model_dir / "policy_checkpoint.npz")
    dataset = load_bc_dataset(args.dataset)
    mean, safe_std = observation_normalizer(dataset)
    from physical_ai_sandbox.learning.bc.dataset import BCDataset, BCSplit

    normalized = BCDataset(
        train=BCSplit(
            normalize_observations(dataset.train.observations, mean, safe_std),
            dataset.train.actions,
            dataset.train.episode_ids,
        ),
        validation=BCSplit(
            normalize_observations(dataset.validation.observations, mean, safe_std),
            dataset.validation.actions,
            dataset.validation.episode_ids,
        ),
        test=BCSplit(
            normalize_observations(dataset.test.observations, mean, safe_std),
            dataset.test.actions,
            dataset.test.episode_ids,
        ),
        metadata=dataset.metadata,
        manifest=dataset.manifest,
        statistics=dataset.statistics,
    )
    report = evaluate_policy(policy, normalized)
    report["model_metadata"] = {
        "trainer_version": metadata.get("trainer_version"),
        "dataset_sample_count": metadata.get("dataset_sample_count"),
        "dataset_episode_count": metadata.get("dataset_episode_count"),
    }
    (model_dir / "evaluation_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
