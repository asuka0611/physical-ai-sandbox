from __future__ import annotations

from dataclasses import dataclass

from physical_ai_sandbox.learning.datasets.feature_encoder import ObservationEncoder
from physical_ai_sandbox.perception.types import ObjectPerception, ObservationMode
from physical_ai_sandbox.robotics.types import RobotState
from physical_ai_sandbox.types import Observation


@dataclass(slots=True)
class BuiltObservation:
    observation: Observation
    metadata: dict[str, object]


class ObservationBuilder:
    def __init__(self, mode: ObservationMode = ObservationMode.SIMULATOR_STATE) -> None:
        self.mode = mode
        self.encoder = ObservationEncoder()

    def build(
        self,
        robot_state: RobotState,
        *,
        perception: ObjectPerception | None = None,
    ) -> BuiltObservation:
        observation: Observation = {**robot_state.observation}
        object_pose_source = "sim_truth" if robot_state.backend == "mujoco_sim" else "mock"
        if self.mode in {ObservationMode.PERCEPTION_RESULT, ObservationMode.HYBRID}:
            if perception is None:
                raise ValueError("perception result is required for perception observation mode")
            observation["cube_position"] = list(perception.position)
            observation["cube_rotation"] = list(perception.rotation)
            object_pose_source = perception.source
        self.encoder.encode(observation)
        return BuiltObservation(
            observation=observation,
            metadata={
                "observation_mode": self.mode.value,
                "execution_backend": robot_state.backend,
                "object_pose_source": object_pose_source,
                "hardware_connected": robot_state.health.hardware_connected,
                "real_world_validated": robot_state.health.real_world_validated,
            },
        )
