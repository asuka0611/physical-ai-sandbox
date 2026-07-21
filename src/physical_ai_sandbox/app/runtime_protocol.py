from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Literal

MessageType = Literal["ready", "status", "error", "shutdown"]


@dataclass(frozen=True, slots=True)
class RuntimeMessage:
    type: MessageType
    payload: dict[str, Any]

    def to_json_line(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True) + "\n"


def encode_message(message_type: MessageType, **payload: Any) -> str:
    return RuntimeMessage(type=message_type, payload=payload).to_json_line()


def decode_message(line: str) -> RuntimeMessage:
    data = json.loads(line)
    if not isinstance(data, dict):
        raise ValueError("Runtime message must be a JSON object")
    message_type = data.get("type")
    if message_type not in {"ready", "status", "error", "shutdown"}:
        raise ValueError(f"Unknown runtime message type: {message_type}")
    payload = data.get("payload", {})
    if not isinstance(payload, dict):
        raise ValueError("Runtime message payload must be a JSON object")
    return RuntimeMessage(type=message_type, payload=payload)
