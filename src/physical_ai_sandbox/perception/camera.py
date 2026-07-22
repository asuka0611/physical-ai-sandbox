from __future__ import annotations

from typing import Any, Protocol

from physical_ai_sandbox.perception.types import CameraFrame, CameraHealth


class CameraSource(Protocol):
    name: str

    def open(self) -> None: ...

    def read(self) -> CameraFrame: ...

    def close(self) -> None: ...

    def health(self) -> CameraHealth: ...

    def metadata(self) -> dict[str, Any]: ...
