from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.evaluation.policy_runner import (
    PolicyEvaluationConfig,
    evaluate_policy,
)
from physical_ai_sandbox.policies.factory import create_policy


def compare_policies(
    policy_names: list[str],
    *,
    model_paths: dict[str, str | Path] | None = None,
    episodes: int = 3,
    seed: int = 42,
    max_steps: int = 200,
    deterministic: bool = True,
    output_dir: str | Path = "logs/policy_comparison",
) -> dict[str, Any]:
    if not policy_names:
        raise ValueError("at least one policy is required")
    model_paths = model_paths or {}
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    reports: dict[str, dict[str, Any]] = {}
    for name in policy_names:
        normalized = name.strip().lower()
        policy = create_policy(normalized, model_path=model_paths.get(normalized), seed=seed)
        report = evaluate_policy(
            policy,
            config=PolicyEvaluationConfig(
                episodes=episodes,
                max_steps=max_steps,
                seed=seed,
                deterministic=deterministic,
                record=False,
                save_trajectory=True,
                log_root=output / normalized,
            ),
            model_path=model_paths.get(normalized),
            output=output / f"{normalized}_evaluation.json",
            csv_output=output / f"{normalized}_episodes.csv",
        )
        reports[normalized] = report
    summary = _summary(reports)
    comparison = {
        "settings": {
            "policies": list(reports),
            "episodes": episodes,
            "seed": seed,
            "max_steps": max_steps,
            "deterministic": deterministic,
            "model_paths": {key: str(value) for key, value in model_paths.items()},
        },
        "summary": summary,
        "reports": reports,
        "warnings": [
            "All policies are compared with the same base seed and episode count.",
            "Random, BC, and PPO results are fixed-condition grasp+lift evaluation only.",
        ],
    }
    (output / "comparison_report.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_summary_csv(summary, output / "comparison_summary.csv")
    _write_markdown(summary, output / "comparison_summary.md")
    return comparison


def _summary(reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, report in reports.items():
        episodes = report["episodes"]
        rewards = [float(item["total_reward"]) for item in episodes]
        lengths = [int(item["episode_length"]) for item in episodes]
        completion_times = [float(item["completion_time"]) for item in episodes]
        failures = Counter(str(item["termination_reason"]) for item in episodes)
        rows.append(
            {
                "policy": name,
                "success_rate": report["metrics"]["success_rate"],
                "mean_reward": float(np.mean(rewards)),
                "reward_std": float(np.std(rewards)),
                "mean_episode_length": float(np.mean(lengths)),
                "mean_completion_time": float(np.mean(completion_times)),
                "failure_reason_counts": dict(sorted(failures.items())),
            },
        )
    return rows


def _write_summary_csv(summary: list[dict[str, Any]], output: str | Path) -> None:
    path = Path(output)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "policy",
                "success_rate",
                "mean_reward",
                "reward_std",
                "mean_episode_length",
                "mean_completion_time",
                "failure_reason_counts",
            ],
        )
        writer.writeheader()
        for row in summary:
            writer.writerow(
                {
                    **row,
                    "failure_reason_counts": json.dumps(
                        row["failure_reason_counts"],
                        sort_keys=True,
                    ),
                },
            )


def _write_markdown(summary: list[dict[str, Any]], output: str | Path) -> None:
    lines = [
        "# Policy Comparison Summary",
        "",
        "| policy | success rate | mean reward | reward std | "
        "mean length | mean completion time | failure reasons |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary:
        lines.append(
            "| {policy} | {success_rate:.3f} | {mean_reward:.3f} | {reward_std:.3f} | "
            "{mean_episode_length:.3f} | {mean_completion_time:.3f} | {failures} |".format(
                failures=json.dumps(row["failure_reason_counts"], sort_keys=True),
                **row,
            ),
        )
    Path(output).write_text("\n".join(lines) + "\n", encoding="utf-8")
