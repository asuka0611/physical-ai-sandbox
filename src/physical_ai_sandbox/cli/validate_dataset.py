from __future__ import annotations

import argparse

from physical_ai_sandbox.learning.datasets.dataset_builder import validate_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a built Phase 2 dataset.")
    parser.add_argument("dataset_dir")
    args = parser.parse_args()
    result = validate_dataset(args.dataset_dir)
    print(
        {
            "dataset_dir": result["dataset_dir"],
            "sample_count": result["sample_count"],
            "splits": result["splits"],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
