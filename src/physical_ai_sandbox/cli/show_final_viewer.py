from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import mujoco.viewer
import numpy as np

from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv


def main() -> int:
    parser = argparse.ArgumentParser(description="Show a saved final state in MuJoCo viewer.")
    parser.add_argument("state_json")
    parser.add_argument("--hold-seconds", type=float, default=1.0)
    args = parser.parse_args()
    payload = json.loads(Path(args.state_json).read_text(encoding="utf-8"))
    env = PandaPickPlaceEnv(config_path=payload["config_path"])
    env.data.qpos[:] = np.array(payload["qpos"], dtype=float)
    env.render()
    with mujoco.viewer.launch_passive(env.model, env.data) as viewer:
        viewer.cam.azimuth = 135
        viewer.cam.elevation = -25
        viewer.cam.distance = 1.35
        viewer.cam.lookat[:] = [0.45, 0.0, 0.55]
        viewer.sync()
        time.sleep(args.hold_seconds)
        viewer.close()
    env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
