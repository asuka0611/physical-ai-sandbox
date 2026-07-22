from __future__ import annotations

from physical_ai_sandbox.learning.datasets.feature_encoder import ObservationEncoder
from physical_ai_sandbox.perception import (
    MockCamera,
    ObjectPerception,
    ObservationBuilder,
    ObservationMode,
)
from physical_ai_sandbox.robotics.mock_robot import MockRealRobot


def test_mock_camera_reads_synthetic_frame_with_provenance() -> None:
    camera = MockCamera(width=64, height=48)
    camera.open()
    try:
        frame = camera.read()
    finally:
        camera.close()

    assert frame.image.shape == (48, 64, 3)
    assert frame.source_kind == "mock"
    assert frame.metadata["provenance"] == "synthetic"
    assert camera.metadata()["hardware_connected"] is False


def test_observation_builder_preserves_schema_and_records_sim_truth_or_mock() -> None:
    robot = MockRealRobot()
    robot.connect()
    state = robot.get_state()

    built = ObservationBuilder().build(state)

    ObservationEncoder().encode(built.observation)
    assert built.metadata["object_pose_source"] == "mock"
    assert built.metadata["real_world_validated"] is False


def test_observation_builder_uses_explicit_perception_result() -> None:
    robot = MockRealRobot()
    robot.connect()
    state = robot.get_state()
    perception = ObjectPerception(
        object_id="cube",
        position=[0.5, 0.1, 0.45],
        rotation=[1.0, 0.0, 0.0, 0.0],
        confidence=0.9,
        source="mock",
    )

    built = ObservationBuilder(ObservationMode.PERCEPTION_RESULT).build(
        state,
        perception=perception,
    )

    assert built.observation["cube_position"] == [0.5, 0.1, 0.45]
    assert built.metadata["object_pose_source"] == "mock"
    ObservationEncoder().encode(built.observation)
