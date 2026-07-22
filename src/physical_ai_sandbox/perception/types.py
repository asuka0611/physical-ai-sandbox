from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class CameraState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    ERROR = "error"


class ObservationMode(Enum):
    SIMULATOR_STATE = "simulator_state"
    PERCEPTION_RESULT = "perception_result"
    HYBRID = "hybrid"


@dataclass(frozen=True, slots=True)
class CameraHealth:
    state: CameraState
    message: str = ""
    latency_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class CameraFrame:
    image: np.ndarray
    timestamp: float
    source_kind: str
    frame_id: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ObjectPerception:
    object_id: str
    position: list[float]
    rotation: list[float]
    confidence: float
    source: str
    latency_seconds: float = 0.0
