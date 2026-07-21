from __future__ import annotations

import argparse
from pathlib import Path

from physical_ai_sandbox.controllers.replay import ReplayController
from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH


def replay_episode(
    episode_dir: str | Path,
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    max_steps: int | None = None,
) -> dict[str, object]:
    env = PandaPickPlaceEnv(config_path=config_path)
    controller = ReplayController(episode_dir)
    observation = env.reset()
    steps = 0
    terminated = False
    truncated = False
    for action in controller.actions():
        observation, _reward, terminated, truncated, _info = env.step(action)
        steps += 1
        if max_steps is not None and steps >= max_steps:
            break
        if terminated or truncated:
            break
    env.close()
    return {
        "steps": steps,
        "terminated": terminated,
        "truncated": truncated,
        "success": observation["is_success"],
        "elapsed_time": observation["elapsed_time"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay a saved Physical AI Sandbox episode.")
    parser.add_argument("episode_dir")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--max-steps", type=int, default=None)
    args = parser.parse_args()
    result = replay_episode(args.episode_dir, config_path=args.config, max_steps=args.max_steps)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
