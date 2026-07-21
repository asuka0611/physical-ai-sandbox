from __future__ import annotations

from pathlib import Path
from typing import Any

from physical_ai_sandbox.controllers.behavior_cloning import BehaviorCloningController
from physical_ai_sandbox.policies.base import PolicyAction
from physical_ai_sandbox.types import Observation


class BehaviorCloningPolicy:
    name = "bc"

    def __init__(self, model_path: str | Path) -> None:
        self.model_path = Path(model_path)
        self.controller = BehaviorCloningController(self.model_path)

    def reset(self, *, seed: int | None = None) -> None:
        del seed

    def act(self, observation: Observation, *, deterministic: bool = True) -> PolicyAction:
        del deterministic
        output = self.controller.act(observation)
        return PolicyAction(
            action=output.action,
            is_safe=output.is_safe,
            unsafe_reason=output.unsafe_reason,
        ).clipped()

    def close(self) -> None:
        return None

    def metadata(self) -> dict[str, Any]:
        return {
            "policy": self.name,
            "model_path": str(self.model_path),
            "checkpoint_path": str(self.controller.checkpoint_path),
            "controller_metadata": self.controller.metadata,
        }
