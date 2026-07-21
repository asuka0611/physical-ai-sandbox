from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.types import Observation


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    return value


class EpisodeRecorder:
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.episode_dir: Path | None = None
        self._steps_file = None
        self.step_count = 0
        self.episode_id: str | None = None
        self.started_at: str | None = None

    @property
    def is_recording(self) -> bool:
        return self._steps_file is not None

    def start(self, metadata: dict[str, Any] | None = None) -> Path:
        if self.is_recording:
            raise RuntimeError("Episode recording is already active")
        now = datetime.now(UTC)
        self.started_at = now.isoformat()
        self.episode_id = now.strftime("episode_%Y%m%d_%H%M%S_%f")
        self.episode_dir = self.root_dir / self.episode_id
        self.episode_dir.mkdir(parents=True, exist_ok=False)
        metadata_payload = {
            "episode_id": self.episode_id,
            "started_at": self.started_at,
            "metadata": metadata or {},
        }
        (self.episode_dir / "metadata.json").write_text(
            json.dumps(_json_safe(metadata_payload), indent=2) + "\n",
            encoding="utf-8",
        )
        self._steps_file = (self.episode_dir / "steps.jsonl").open("w", encoding="utf-8")
        self.step_count = 0
        return self.episode_dir

    def record_step(
        self,
        observation: Observation,
        action: list[float],
        reward: float,
        time_seconds: float,
        success: bool,
        grasp_state: bool,
        info: dict[str, Any] | None = None,
    ) -> None:
        if not self.is_recording or self._steps_file is None or self.episode_id is None:
            return
        payload = {
            "episode_id": self.episode_id,
            "step": self.step_count,
            "time": time_seconds,
            "observation": observation,
            "action": action,
            "reward": reward,
            "success": success,
            "grasp_state": grasp_state,
            "info": info or {},
        }
        self._steps_file.write(json.dumps(_json_safe(payload), separators=(",", ":")) + "\n")
        self._steps_file.flush()
        self.step_count += 1

    def stop(self, summary: dict[str, Any] | None = None) -> Path:
        if not self.is_recording or self._steps_file is None or self.episode_dir is None:
            raise RuntimeError("Episode recording is not active")
        self._steps_file.close()
        self._steps_file = None
        summary_payload = {
            "episode_id": self.episode_id,
            "started_at": self.started_at,
            "stopped_at": datetime.now(UTC).isoformat(),
            "steps": self.step_count,
            "summary": summary or {},
        }
        (self.episode_dir / "summary.json").write_text(
            json.dumps(_json_safe(summary_payload), indent=2) + "\n",
            encoding="utf-8",
        )
        return self.episode_dir
