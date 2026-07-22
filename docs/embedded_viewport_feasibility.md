# Embedded Viewport Feasibility

## Decision

Do not embed the official MuJoCo Viewer into Tkinter in this pass.

## Reason

The stable Phase 4.6 architecture depends on separating Tkinter in normal Python from MuJoCo Viewer in an `mjpython` process. Recombining them or forcing the GLFW/AppKit window into Tk risks reviving the same macOS main-thread and Tcl/Tk crash class.

## Adopted Phase 5.4 MVP

- Keep the two-process UI/Viewer architecture.
- Provide workspace-style UI organization.
- Provide Viewer front and position reset controls on macOS.
- Keep offscreen rendering as a future technical experiment.

## Future Feasibility Criteria

A future embedded viewport must measure FPS, p95 frame time, CPU, memory growth, camera interaction latency, resize behavior, Retina behavior, and 10-minute stability before adoption.
