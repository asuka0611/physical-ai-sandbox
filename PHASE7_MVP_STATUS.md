# Phase 7 MVP Status

Last updated: 2026-07-22

Phase 7 is implemented as a perception pipeline foundation only.

## Implemented

- `CameraSource` protocol.
- `MockCamera` synthetic RGB frame source.
- `ObjectPerception` model.
- `ObservationBuilder` for simulator/mock/perception-derived object state.
- Provenance metadata to avoid treating simulator truth or mock data as real vision.
- Automated tests for mock camera and observation building.

## Not Implemented

- Real camera capture.
- OpenCV or learned object detection.
- Full Viewer preview overlay.
