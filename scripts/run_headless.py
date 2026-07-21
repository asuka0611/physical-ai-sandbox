from __future__ import annotations

import argparse

import numpy as np

from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the sandbox without a viewer.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()

    env = PandaPickPlaceEnv(config_path=args.config)
    if args.record:
        print(f"Recording to {env.start_recording({'mode': 'headless'})}")
    observation = env.reset()
    for step in range(args.steps):
        action = np.zeros(8, dtype=float)
        action[step % 7] = 0.1
        observation, reward, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            print(f"Stopped at step={step} reward={reward:.3f} info={info}")
            break
    if args.record:
        print(f"Summary written to {env.stop_recording({'mode': 'headless'})}")
    env.close()
    print(
        {
            "elapsed_time": observation["elapsed_time"],
            "success": observation["is_success"],
            "cube_position": observation["cube_position"],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
