# Robot Visual Language

Phase 5.5 improves the Panda-style robot so the joint structure is easier to read.

## Implemented MVP

- Visual-only motor housing geoms for J1-J7.
- `joint1_label_site` through `joint7_label_site` markers.
- Blue motor housings, light robot shell, and yellow joint label sites.
- Visual geometry remains collision-disabled and does not change the 8D Action or Observation contract.
- UI Robot Inspector lists J1-J7 with human-readable joint names and Focus actions.

## Current Limits

- Full 3D text labels are not implemented because the official MuJoCo viewer does not expose a simple stable 3D text API.
- Selected-joint highlight is reported through snapshot/overlay status first; dynamic 3D highlight markers remain future work.
