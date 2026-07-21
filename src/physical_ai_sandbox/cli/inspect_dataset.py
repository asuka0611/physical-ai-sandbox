from __future__ import annotations

import argparse
import json
from pathlib import Path

from physical_ai_sandbox.learning.datasets.dataset_builder import validate_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a built Phase 2 dataset.")
    parser.add_argument("dataset_dir")
    args = parser.parse_args()
    dataset_dir = Path(args.dataset_dir)
    validation = validate_dataset(dataset_dir)
    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    quality = json.loads((dataset_dir / "quality_report.json").read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "dataset_name": manifest["dataset_name"],
                "dataset_version": manifest["dataset_version"],
                "sample_count": validation["sample_count"],
                "episode_count": manifest["episode_count"],
                "success_rate": quality["success_rate"],
                "splits": validation["splits"],
                "broken_episodes": quality.get("broken_episodes", {}),
            },
            indent=2,
            sort_keys=True,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
