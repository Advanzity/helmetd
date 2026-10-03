# Compute application

Planned C++20/OpenCV application on the Mac. No runtime implemented yet.

Planned modules:

| Module | Responsibility |
| --- | --- |
| Ingest | Receive camera frames, sensor samples, and available pose observations. |
| Tracking | Estimate or consume head pose; report confidence and tracking loss. |
| Scene | Maintain world coordinates, anchor identities, and HUD state. |
| Output | Publish poses, anchors, and HUD state to the local renderer. |
| Runtime | Configuration, clock exchange, diagnostics, and a local preview. |

Start with a single marker-based anchor and synthetic sensor input. Introduce
additional perception only after spatial alignment and latency are measured.

Keep tracking and scene state separable so recorded input can be replayed
without connected hardware. Rendering lives in the separate
[HUD project](../hud/README.md).

Read the shared [protocol plan](../../packages/protocol/README.md) before adding
device messages. Setup and run commands will be documented after implementation.
