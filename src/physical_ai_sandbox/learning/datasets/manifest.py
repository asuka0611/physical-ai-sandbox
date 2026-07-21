from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from physical_ai_sandbox.learning.datasets.feature_encoder import (
    ACTION_SCHEMA_VERSION,
    OBSERVATION_SCHEMA_VERSION,
)

BUILDER_VERSION = "phase2.dataset_builder.v1"


def git_commit(repo_root: str | Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def build_manifest(
    *,
    dataset_name: str,
    dataset_version: str,
    source_episodes: list[str],
    split_seed: int,
    split_ratio: tuple[float, float, float],
    feature_order: list[str],
    sample_count: int,
    episode_count: int,
    success_episode_count: int,
    failure_episode_count: int,
    repo_root: str | Path,
) -> dict[str, Any]:
    return {
        "dataset_name": dataset_name,
        "dataset_version": dataset_version,
        "created_at": datetime.now(UTC).isoformat(),
        "source_episodes": source_episodes,
        "observation_schema_version": OBSERVATION_SCHEMA_VERSION,
        "action_schema_version": ACTION_SCHEMA_VERSION,
        "split_seed": split_seed,
        "split_ratio": {
            "train": split_ratio[0],
            "validation": split_ratio[1],
            "test": split_ratio[2],
        },
        "feature_order": feature_order,
        "sample_count": sample_count,
        "episode_count": episode_count,
        "success_episode_count": success_episode_count,
        "failure_episode_count": failure_episode_count,
        "git_commit": git_commit(repo_root),
        "builder_version": BUILDER_VERSION,
    }
