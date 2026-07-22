from __future__ import annotations

import time
from typing import Any

import numpy as np

from physical_ai_sandbox.perception.types import CameraFrame, CameraHealth, CameraState


class MockCamera:
    name = "mock_camera"

    def __init__(self, *, width: int = 320, height: int = 240, seed: int = 42) -> None:
        self.width = int(width)
        self.height = int(height)
        self._rng = np.random.default_rng(seed)
        self._open = False
        self._frame_id = 0
        self._health = CameraHealth(CameraState.CLOSED)

    def open(self) -> None:
        self._open = True
        self._health = CameraHealth(CameraState.OPEN, "synthetic mock camera")

    def read(self) -> CameraFrame:
        if not self._open:
            raise RuntimeError("MockCamera is not open")
        start = time.perf_counter()
        image = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        cx = int(self.width * 0.55)
        cy = int(self.height * 0.48)
        image[max(0, cy - 8) : cy + 8, max(0, cx - 8) : cx + 8, :] = [255, 128, 32]
        self._frame_id += 1
        latency = time.perf_counter() - start
        self._health = CameraHealth(CameraState.OPEN, "synthetic mock camera", latency)
        return CameraFrame(
            image=image,
            timestamp=time.time(),
            source_kind="mock",
            frame_id=self._frame_id,
            metadata={"provenance": "synthetic", "camera_source": "mock"},
        )

    def close(self) -> None:
        self._open = False
        self._health = CameraHealth(CameraState.CLOSED)

    def health(self) -> CameraHealth:
        return self._health

    def metadata(self) -> dict[str, Any]:
        return {
            "camera_source": "mock",
            "hardware_connected": False,
            "real_world_validated": False,
            "resolution": [self.width, self.height],
        }
