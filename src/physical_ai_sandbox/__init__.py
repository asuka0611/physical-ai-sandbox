"""Physical AI Sandbox package."""

from __future__ import annotations

__all__ = ["PandaPickPlaceEnv"]


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    if name == "PandaPickPlaceEnv":
        from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv

        return PandaPickPlaceEnv
    raise AttributeError(name)
