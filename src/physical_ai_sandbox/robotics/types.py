from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from physical_ai_sandbox.types import Observation


class RobotConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    EMERGENCY_STOPPED = "emergency_stopped"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class RobotHealth:
    state: RobotConnectionState
    message: str = ""
    latency_seconds: float = 0.0
    hardware_connected: bool = False
    real_world_validated: bool = False


@dataclass(frozen=True, slots=True)
class RobotState:
    observation: Observation
    timestamp: float
    backend: str
    health: RobotHealth
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RobotCommandResult:
    applied_action: np.ndarray
    accepted: bool
    reason: str | None
    state: RobotState | None = None
