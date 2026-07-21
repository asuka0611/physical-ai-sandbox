from __future__ import annotations

import time

from physical_ai_sandbox.viewer_runtime import require_mjpython_on_macos


def _print_controls() -> None:
    print("Controls: 1-7 select joint, Tab/] next, [ previous, Left/Right move")
    print("Space gripper, R reset, P pause, L record, C reset camera, Esc quit")


def main() -> int:
    require_mjpython_on_macos()

    import mujoco.viewer

    from physical_ai_sandbox.controllers.manual import ManualController
    from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv

    env = PandaPickPlaceEnv()
    controller = ManualController()
    _print_controls()

    def key_callback(key: int) -> None:
        before = controller.last_event
        controller.handle_key(key)
        if controller.last_event != before:
            print(controller.last_event)

    with mujoco.viewer.launch_passive(env.model, env.data, key_callback=key_callback) as viewer:
        while viewer.is_running() and not controller.quit_requested:
            if controller.reset_requested:
                env.reset()
                controller.reset_requested = False
            if controller.camera_reset_requested:
                viewer.cam.azimuth = 135
                viewer.cam.elevation = -25
                viewer.cam.distance = 1.35
                viewer.cam.lookat[:] = [0.45, 0.0, 0.55]
                controller.camera_reset_requested = False
            if controller.record_toggle_requested:
                if env.recorder.is_recording:
                    print(f"Episode saved: {env.stop_recording({'mode': 'manual'})}")
                else:
                    print(f"Recording: {env.start_recording({'mode': 'manual'})}")
                controller.record_toggle_requested = False
            if not controller.paused:
                observation, reward, terminated, _truncated, info = env.step(controller.action())
                if terminated:
                    print(
                        "Episode ended "
                        f"success={observation['is_success']} reward={reward:.3f} info={info}"
                    )
                    env.reset()
            viewer.sync()
            time.sleep(env.dt)

    env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
