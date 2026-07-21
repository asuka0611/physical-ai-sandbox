from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv
from physical_ai_sandbox.viewer_runtime import mjpython_path

PLACE_POSE = np.array([-2.6057, -1.6142, 2.2971, -0.9972, -0.1489, 1.0023, -1.7766])


def _drive_to_pose(env: PandaPickPlaceEnv, pose: np.ndarray) -> None:
    while np.max(np.abs(env.target_joint_positions - pose)) > 0.02:
        delta = np.clip((pose - env.target_joint_positions) / env.joint_delta_scale, -1.0, 1.0)
        action = np.zeros(8, dtype=float)
        action[:7] = delta
        action[7] = 1.0 if env.gripper_target <= env.gripper_closed + 1e-6 else -1.0
        env.step(action)


def _launch_viewer_process(env: PandaPickPlaceEnv, hold_seconds: float) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as file:
        state_path = Path(file.name)
        json.dump(
            {
                "config_path": str(env.config_path),
                "qpos": env.data.qpos.astype(float).tolist(),
            },
            file,
        )
    command = [
        mjpython_path(),
        "-m",
        "physical_ai_sandbox.cli.show_final_viewer",
        str(state_path),
        "--hold-seconds",
        str(hold_seconds),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=max(hold_seconds + 8.0, 10.0))
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate(timeout=3.0)
    state_path.unlink(missing_ok=True)
    return {
        "viewer_process_exitcode": process.returncode,
        "viewer_process_timed_out": timed_out,
        "viewer_stdout": stdout.strip(),
        "viewer_stderr_tail": stderr.strip().splitlines()[-3:],
    }

def run_demo(
    show_viewer: bool,
    record: bool,
    hold_seconds: float = 1.0,
) -> dict[str, object]:
    env = PandaPickPlaceEnv()
    if record:
        env.start_recording({"mode": "pick_place_demo"})
    env.reset()

    for _ in range(10):
        env.step([0, 0, 0, 0, 0, 0, 0, -1])
    for _ in range(10):
        env.step([0, 0, 0, 0, 0, 0, 0, 1])
    grasped_after_close = env.is_grasped
    _drive_to_pose(env, PLACE_POSE)
    lifted_position = env._observation()["cube_position"]
    for _ in range(8):
        env.step([0, 0, 0, 0, 0, 0, 0, -1])
    final_observation = env._observation()
    settle_steps = int((env.evaluator.stable_seconds + 1.0) / env.dt)
    for _ in range(settle_steps):
        final_observation, _reward, terminated, _truncated, _info = env.step(np.zeros(8))
        if terminated:
            break

    result: dict[str, object] = {
        "grasped_after_close": grasped_after_close,
        "lifted_position": lifted_position,
        "final_cube_position": final_observation["cube_position"],
        "success": final_observation["is_success"],
        "elapsed_time": final_observation["elapsed_time"],
    }
    if show_viewer:
        result.update(_launch_viewer_process(env, hold_seconds))
    if record:
        episode_dir = env.stop_recording({"mode": "pick_place_demo", **result})
        result["episode_dir"] = str(episode_dir)
    env.close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a visual pick-and-place smoke demo.")
    parser.add_argument(
        "--viewer",
        action="store_true",
        help="Show the MuJoCo viewer final state while running.",
    )
    parser.add_argument("--record", action="store_true", help="Save an episode log.")
    parser.add_argument("--hold-seconds", type=float, default=1.0)
    args = parser.parse_args()
    print(
        run_demo(
            show_viewer=args.viewer,
            record=args.record,
            hold_seconds=args.hold_seconds,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
