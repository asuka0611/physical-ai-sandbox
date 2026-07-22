# Embedded Viewport Feasibility

## Decision

Do not embed the official MuJoCo Viewer/GLFW window into Tkinter. Use an
offscreen MuJoCo renderer in the `mjpython` simulation process and draw streamed
frames inside the Tk workspace instead.

## Reason

The stable Phase 4.6 architecture depends on separating Tkinter in normal Python
from MuJoCo/AppKit work in an `mjpython` process. Recombining them or forcing the
GLFW/AppKit window into Tk risks reviving the same macOS main-thread and
Tcl/Tk crash class.

## Adopted Phase 5.4 Implementation

- Keep the two-process UI/simulation architecture.
- Provide workspace-style UI organization.
- Render MuJoCo RGB frames offscreen with `mujoco.Renderer`.
- Encode frames as PPM and send them over the existing localhost IPC channel.
- Display frames directly in the central Tk Canvas named 3D Viewport.
- Remove the external MuJoCo Viewer window from the ControlPanel path.

## Future Feasibility Criteria

A production-grade embedded viewport must still measure FPS, p95 frame time,
CPU, memory growth, camera interaction latency, resize behavior, Retina
behavior, and 10-minute stability before being treated as complete.
