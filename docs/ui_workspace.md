# UI Workspace and Recovery

Phase 5.1-5.9 starts the transition from a demo-style control panel to a Physical AI workspace.

## Implemented MVP

- Dock-style Tk workspace with toolbar, scene/policy sidebar, viewer management area, robot inspector, and bottom Console/Metrics/Evaluation/Timeline tabs.
- Central `InputManager` for keyboard focus and shortcut dispatch.
- Text entry focus blocks robot shortcuts such as W/A/S/D and Space.
- Escape clears text focus instead of quitting the app.
- Toolbar controls for Reset, Restart Viewer, Restart All, Emergency Stop, and Camera Reset.
- macOS best-effort Viewer front/position commands without `shell=True`.
- Background evaluation subprocess from the Evaluation tab.
- Viewer process restart loop guard.

## Current Limits

- MuJoCo Viewer remains a separate `mjpython` process for stability.
- Native one-window embedding is not adopted in this pass.
- Viewer positioning is best-effort on macOS and may depend on Accessibility permission.
- Timeline replay UI is a placeholder; action trajectories are saved by policy evaluation JSON.
- Long-run memory verification still requires manual testing.
