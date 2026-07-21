from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path


class ReplayController:
    def __init__(self, episode_dir: str | Path) -> None:
        self.episode_dir = Path(episode_dir)
        self.steps_path = self.episode_dir / "steps.jsonl"
        if not self.steps_path.exists():
            raise FileNotFoundError(f"Replay steps file not found: {self.steps_path}")

    def actions(self) -> Iterator[list[float]]:
        with self.steps_path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                payload = json.loads(line)
                action = payload.get("action")
                if not isinstance(action, list) or len(action) != 8:
                    raise ValueError(f"Invalid action at {self.steps_path}:{line_number}")
                yield [float(value) for value in action]
