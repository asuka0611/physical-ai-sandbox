from __future__ import annotations

from physical_ai_sandbox.cli.pick_place_demo import run_demo


def test_pick_place_demo_grasps_lifts_places_and_succeeds() -> None:
    result = run_demo(show_viewer=False, record=False)
    assert result["grasped_after_close"] is True
    assert result["lifted_position"][2] > 0.45
    assert result["success"] is True
