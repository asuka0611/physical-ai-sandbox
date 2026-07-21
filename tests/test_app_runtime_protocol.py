from __future__ import annotations

import pytest

from physical_ai_sandbox.app.runtime_protocol import decode_message, encode_message


def test_runtime_protocol_round_trips_json_line() -> None:
    line = encode_message("status", step=12, state="running")
    message = decode_message(line)

    assert message.type == "status"
    assert message.payload == {"step": 12, "state": "running"}


def test_runtime_protocol_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="Unknown runtime message type"):
        decode_message('{"type": "unknown", "payload": {}}')
