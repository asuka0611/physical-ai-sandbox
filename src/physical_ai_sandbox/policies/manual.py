from __future__ import annotations

from typing import Any

import numpy as np

from physical_ai_sandbox.learning.datasets.feature_encoder import ACTION_DIMENSION
from physical_ai_sandbox.policies.base import PolicyAction
from physical_ai_sandbox.types import Observation


class ManualPolicy:
    """Placeholder adapter for the shared Policy contract.

    Manual control remains driven by the Tk control panel. Automated batch
    evaluation intentionally returns a zero action unless an external UI action
    source is added later.
    """

    name = "manual"

    def reset(self, *, seed: int | None = None) -> None:
        del seed

    def act(self, observation: Observation, *, deterministic: bool = True) -> PolicyAction:
        del observation, deterministic
        return PolicyAction(action=np.zeros(ACTION_DIMENSION, dtype=np.float64))

    def close(self) -> None:
        return None

    def metadata(self) -> dict[str, Any]:
        return {"policy": self.name, "automated_batch_supported": False}
