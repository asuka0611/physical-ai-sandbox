# UI Workspace and Recovery

Phase 5.1-5.9 starts the transition from a demo-style control panel to a Physical AI workspace.

## Implemented MVP

- Dock-style Tk workspace with toolbar, scene/policy sidebar, embedded 3D Viewport, robot inspector, and bottom Console/Metrics/Evaluation/Timeline tabs.
- Central `InputManager` for keyboard focus and shortcut dispatch.
- Text entry focus blocks robot shortcuts such as W/A/S/D and Space.
- Escape clears text focus instead of quitting the app.
- Toolbar controls for Reset, Restart Viewport, Restart All, Emergency Stop, and Camera Reset.
- MuJoCo offscreen RGB frames are streamed from the `mjpython` simulation process into the central Tk Canvas.
- Background evaluation subprocess from the Evaluation tab.
- Viewport process restart loop guard.

## Current Limits

- The official MuJoCo Viewer window is not opened from the ControlPanel path.
- The embedded Viewport is frame-stream based and does not yet expose native Viewer menus or mouse picking.
- Timeline replay UI is a placeholder; action trajectories are saved by policy evaluation JSON.
- Long-run memory verification still requires manual testing.
