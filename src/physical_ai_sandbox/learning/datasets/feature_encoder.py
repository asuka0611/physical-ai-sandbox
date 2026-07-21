from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

OBSERVATION_FIELD_ORDER: tuple[tuple[str, int], ...] = (
    ("joint_positions", 7),
    ("joint_velocities", 7),
    ("gripper_positions", 2),
    ("cube_position", 3),
    ("cube_rotation", 4),
    ("end_effector_position", 3),
    ("is_grasped", 1),
    ("is_success", 1),
    ("elapsed_time", 1),
)
OBSERVATION_SCHEMA_VERSION = "phase1.observation.v1"
ACTION_SCHEMA_VERSION = "phase1.action.v1"
ACTION_DIMENSION = 8


@dataclass(frozen=True, slots=True)
class EncodedObservation:
    vector: np.ndarray
    feature_order: list[str]


class ObservationEncoder:
    schema_version = OBSERVATION_SCHEMA_VERSION

    @property
    def feature_order(self) -> list[str]:
        names: list[str] = []
        for field, length in OBSERVATION_FIELD_ORDER:
            if length == 1:
                names.append(field)
            else:
                names.extend(f"{field}_{index}" for index in range(length))
        return names

    @property
    def dimension(self) -> int:
        return len(self.feature_order)

    def encode(self, observation: dict[str, Any]) -> np.ndarray:
        values: list[float] = []
        for field, expected_length in OBSERVATION_FIELD_ORDER:
            if field not in observation:
                raise ValueError(f"Observation missing required field: {field}")
            raw_value = observation[field]
            if isinstance(raw_value, bool):
                field_values = [1.0 if raw_value else 0.0]
            elif isinstance(raw_value, int | float):
                field_values = [float(raw_value)]
            elif isinstance(raw_value, list):
                field_values = [float(value) for value in raw_value]
            else:
                raise ValueError(
                    f"Observation field {field} has unsupported type {type(raw_value)}",
                )
            if len(field_values) != expected_length:
                raise ValueError(
                    f"Observation field {field} has length {len(field_values)}, "
                    f"expected {expected_length}",
                )
            values.extend(field_values)
        vector = np.array(values, dtype=np.float64)
        if vector.shape != (self.dimension,):
            raise ValueError(
                f"Encoded observation shape {vector.shape}, expected {(self.dimension,)}",
            )
        if not np.all(np.isfinite(vector)):
            raise ValueError("Encoded observation contains NaN or Inf")
        return vector


def validate_action(action: Any) -> np.ndarray:
    if not isinstance(action, list):
        raise ValueError(f"Action must be a list, got {type(action)}")
    array = np.array(action, dtype=np.float64)
    if array.shape != (ACTION_DIMENSION,):
        raise ValueError(f"Action shape {array.shape}, expected {(ACTION_DIMENSION,)}")
    if not np.all(np.isfinite(array)):
        raise ValueError("Action contains NaN or Inf")
    return array
