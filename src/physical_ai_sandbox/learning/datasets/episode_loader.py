from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from physical_ai_sandbox.learning.datasets.episode_dataset import EpisodeRecord, EpisodeStep

REQUIRED_EPISODE_FILES = ("metadata.json", "steps.jsonl", "summary.json")


class EpisodeLoadError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EpisodeScanResult:
    episodes: list[EpisodeRecord]
    errors: dict[str, str]


class EpisodeLoader:
    def load_episode(self, episode_dir: str | Path) -> EpisodeRecord:
        path = Path(episode_dir)
        if not path.is_dir():
            raise EpisodeLoadError(f"Episode path is not a directory: {path}")
        missing = [name for name in REQUIRED_EPISODE_FILES if not (path / name).exists()]
        if missing:
            raise EpisodeLoadError(
                f"Episode {path.name} missing required files: {', '.join(missing)}",
            )
        metadata = self._read_json(path / "metadata.json")
        summary = self._read_json(path / "summary.json")
        episode_id = str(metadata.get("episode_id") or summary.get("episode_id") or path.name)
        steps = self._read_steps(path / "steps.jsonl", episode_id)
        if not steps:
            raise EpisodeLoadError(f"Episode {episode_id} contains no steps")
        return EpisodeRecord(
            episode_id=episode_id,
            path=path,
            metadata=metadata,
            summary=summary,
            steps=steps,
        )

    def scan(self, episodes_root: str | Path) -> EpisodeScanResult:
        root = Path(episodes_root)
        if not root.exists():
            raise EpisodeLoadError(f"Episodes root does not exist: {root}")
        episode_dirs = sorted(path for path in root.iterdir() if path.is_dir())
        episodes: list[EpisodeRecord] = []
        errors: dict[str, str] = {}
        for episode_dir in episode_dirs:
            try:
                episodes.append(self.load_episode(episode_dir))
            except EpisodeLoadError as error:
                errors[episode_dir.name] = str(error)
        return EpisodeScanResult(episodes=episodes, errors=errors)

    def load_many(
        self,
        episodes_root: str | Path,
        *,
        include_broken: bool = False,
    ) -> list[EpisodeRecord]:
        result = self.scan(episodes_root)
        if result.errors and not include_broken:
            messages = "\n".join(
                f"{episode_id}: {error}" for episode_id, error in result.errors.items()
            )
            raise EpisodeLoadError(f"Broken episodes detected:\n{messages}")
        return result.episodes

    @staticmethod
    def successful(episodes: list[EpisodeRecord]) -> list[EpisodeRecord]:
        return [episode for episode in episodes if episode.is_success]

    @staticmethod
    def failed(episodes: list[EpisodeRecord]) -> list[EpisodeRecord]:
        return [episode for episode in episodes if not episode.is_success]

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise EpisodeLoadError(f"Invalid JSON in {path}: {error}") from error
        if not isinstance(data, dict):
            raise EpisodeLoadError(f"JSON file must contain an object: {path}")
        return data

    @staticmethod
    def _read_steps(path: Path, expected_episode_id: str) -> list[EpisodeStep]:
        steps: list[EpisodeStep] = []
        with path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    raise EpisodeLoadError(
                        f"Invalid JSONL at {path}:{line_number}: {error}",
                    ) from error
                if not isinstance(payload, dict):
                    raise EpisodeLoadError(
                        f"Step payload must be an object at {path}:{line_number}",
                    )
                try:
                    episode_id = str(payload["episode_id"])
                    step_index = int(payload["step"])
                    timestamp = float(payload["time"])
                    observation = payload["observation"]
                    action = payload["action"]
                    reward = float(payload["reward"])
                    success = bool(payload["success"])
                except KeyError as error:
                    raise EpisodeLoadError(
                        f"Step at {path}:{line_number} missing field: {error.args[0]}",
                    ) from error
                if episode_id != expected_episode_id:
                    raise EpisodeLoadError(
                        f"Step at {path}:{line_number} has episode_id {episode_id}, "
                        f"expected {expected_episode_id}",
                    )
                if not isinstance(observation, dict):
                    raise EpisodeLoadError(f"Observation must be an object at {path}:{line_number}")
                if not isinstance(action, list):
                    raise EpisodeLoadError(f"Action must be a list at {path}:{line_number}")
                info = payload.get("info", {})
                failure_reason = info.get("failure_reason") if isinstance(info, dict) else None
                steps.append(
                    EpisodeStep(
                        episode_id=episode_id,
                        step_index=step_index,
                        timestamp=timestamp,
                        observation=observation,
                        action=action,
                        reward=reward,
                        terminated=bool(success or failure_reason),
                        truncated=bool(failure_reason == "time limit exceeded"),
                        success=success,
                    ),
                )
        return steps
