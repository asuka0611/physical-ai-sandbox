from __future__ import annotations

import argparse

from physical_ai_sandbox.learning.datasets.dataset_builder import DatasetBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Phase 2 dataset from episode logs.")
    parser.add_argument("--episodes", default="logs/episodes")
    parser.add_argument("--output", default="datasets/pick_place_v1")
    parser.add_argument("--name", default="pick_place")
    parser.add_argument("--version", default="v1")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail when broken episodes are found.",
    )
    args = parser.parse_args()
    builder = DatasetBuilder(seed=args.seed)
    result = builder.build_from_episodes(
        args.episodes,
        args.output,
        dataset_name=args.name,
        dataset_version=args.version,
        allow_broken=not args.strict,
    )
    print(
        {
            "output_dir": str(result.output_dir),
            "sample_count": result.manifest["sample_count"],
            "episode_count": result.manifest["episode_count"],
            "broken_episode_count": len(result.quality_report.get("broken_episodes", {})),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
