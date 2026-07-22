# Perception Pipeline MVP

Phase 7 MVP adds camera and observation-building interfaces without claiming real camera perception.

## Implemented

- `CameraSource` protocol.
- `MockCamera` synthetic RGB frame source.
- `ObjectPerception` data model.
- `ObservationBuilder` that can build existing fixed-schema Observations from simulator/mock state or explicit perception results.
- Provenance fields such as `camera_source`, `object_pose_source`, `hardware_connected`, and `real_world_validated`.

## Not Implemented

- Real camera capture.
- OpenCV object detection.
- Learned perception models.
- Production calibration.
