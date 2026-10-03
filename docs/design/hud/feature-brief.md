# Motorcycle HUD feature brief

Source: the user's [hackathon feature list](../../product/hackathon-features.txt),
preserved verbatim, including its original checkboxes. Checkbox states are source
notes, not independent verification of hardware or implementation. This brief
turns that list into a proposed HUD interaction model and staged demo scope.

## Core interaction

Keep normal riding sparse. Expand the relevant information when a signal,
detected event, or rider command requires it. Speed, gear, and the next navigation
instruction occupy consistent locations; the center stays open. A side-camera
view is a temporary inset, not a replacement for the forward view.

The revised concepts show [normal riding](ride-normal-v1.png) and an
[occupied left blind spot](ride-left-blind-spot-v1.png). Their speed, gear, battery,
route, vehicle, and warnings are illustrative. The road is scene context; only
the HUD graphics and camera inset would be rendered into the glasses. The white
footer belongs to the design presentation and is excluded from the runtime HUD.

The [additional state gallery](extended-states.md) now covers rear threat,
reported hazard, crash countdown, and group riding. A separate
[civic dashboard concept](../civic/README.md) covers aggregate reporting.
The [3D map concepts](3d-map.md) add an optional compact route map and a stationary
route-comparison view, both distinct from calibrated world-anchored road graphics.

## HUD states

| State / trigger | Display | Exit / failure behavior |
| --- | --- | --- |
| Normal | Speed, gear, next maneuver and distance; small connection/battery indicators | Preserve layout when a contextual element appears |
| Left signal | Left camera inset, left signal state; highlight tracked vehicles inside that camera image | Close when signal clears unless an active alert keeps it relevant |
| Right signal | Mirror the left-camera behavior on the right | Same exit rules |
| Blind spot occupied | Directional warning plus the associated camera highlight | Clear only on fresh state showing the alert ended; stale input becomes unavailable |
| Rear threat | Rear-direction warning; optional rear-camera inset selected by urgency | Yield only to a more urgent event; resume ordinary layout when resolved |
| Road hazard | Short hazard type and direction; route distance only when location supports it | Expire or clear from the current state; do not keep obsolete warnings |
| Camera / telemetry / link unavailable | Explicit unavailable state for affected information | Never present a frozen camera as live or missing detection as 'clear' |
| Voice interaction | Small listening/thinking/speaking state and a brief reply when useful | Hide ordinary replies during higher-priority alerts |
| Event saved | Brief recording acknowledgement | Appear only after the recorder confirms the save |
| Probable crash demo | Distinct countdown/cancel state and event-save status | Show an emergency packet on the Mac; no emergency-service contact |

## Arbitration rules

Proposed ordering: urgent validated event, contextual blind-spot/rear warning,
navigation, routine telemetry, then ordinary assistant responses. Rear threats
and road hazards do not get a fixed ordering against each other: an explicit
urgency value and stable tie-breaking rule choose the primary warning. Keep
secondary direction indicators available without stacking large banners.

Use one primary camera inset at a time. Keep its source label visible during
switches. Suppress repeated voice alerts for the same event, and add measured
entry/exit persistence to prevent flicker. Tune thresholds using recorded cases;
these concepts do not establish validated warning thresholds or distance estimates.

Each input needs a timestamp, validity, and source. A connection icon alone is
not evidence that camera frames or telemetry are fresh. Represent unavailable
speed or gear explicitly; do not silently substitute zero. Route guidance, live
turn signals, and detected threats remain separate inputs.

## Fixed and world-anchored elements

The user's world-anchored graphics goal remains part of the project. Fixed
status text, navigation instructions, and camera panels can be developed while
pose access and camera-to-eye calibration are being proved. Detection boxes in
a camera inset use that image's coordinates. Boxes attached to physical vehicles
or arrows attached to the road require the separate calibrated spatial pipeline;
an inset detection is not enough to claim that capability.

## Where the features belong

| Existing component | Proposed responsibility |
| --- | --- |
| `apps/capture` on Pi | Left/right/rear frames, IMU/GPS, bike telemetry and physical save-button inputs, timestamps |
| `apps/compute` on Mac | Tracking, zone occupancy, navigation state, event rules, alert selection, recorder coordination |
| `apps/hud` on Mac | Render the selected state, camera insets, labels, data freshness, and voice state |
| `apps/display` on Pi | Present returned HUD frames and handle stale or disconnected output |
| `apps/voice` on Mac | Conversation, spoken alerts, and future explicit command handling |
| `packages/llm` | Selectable conversational reasoning provider; no dependency in time-critical warning rules |
| `packages/protocol` | Camera identity, timestamps, telemetry validity, object tracks, alert IDs, recorder state |

These are implementation assignments, not claims that these features are built.
The three cameras are left, right, and rear. Forward road-hazard and intersection
coverage must be demonstrated from the actual mounting/views or another source;
the HUD artwork's forward road view does not imply a fourth camera exists.

## Proposed hackathon build order

1. Build a Mac HUD state simulator: normal, left/right signals, blind-spot
   occupancy, rear threat, hazard, stale inputs, voice state, and recorder result.
   Use keyboard controls and explicitly identified simulated telemetry.
2. Feed that same state into the existing Mac-to-Pi video path and prove output
   through the glasses. Continue the separate world-anchor calibration milestone.
3. Replace one simulated camera with a Pi feed, then add the other two. Measure
   simultaneous uplink/downlink behavior before assuming the full rig fits.
4. Add detection/tracking for one vehicle class and left/right zones. Demonstrate
   signal-driven camera selection, occupied-zone warnings, and input loss using
   recorded or controlled scenes. Expand classes after this path works.
5. Add a rear-approach demo and a manual event save with synchronized metadata.
   Then extend recording to the requested 30 seconds before and after an event.
6. If time remains, demonstrate one GPS-tagged hazard and a second simulated
   rider receiving it. Add the probable-crash packet as a clearly separate demo.

The original 24-hour checklist is a broader backlog than this initial slice.
Real CAN integration, quantitative distance/closing speed, full routing, automatic
crash classification, group riding, crowdsourcing, and civic heatmaps remain
planned extensions. Simulated data should remain visibly distinct in the demo.

First acceptance sequence: normal HUD -> left signal -> left camera -> occupied
zone warning -> higher-priority injected event -> recovery -> event-save
acknowledgement -> camera disconnect showing unavailable rather than a frozen view.
The same inputs should produce the same alert selection with the LLM disconnected.

## Dependencies to resolve before live feature claims

- Exact camera models, interfaces, stream formats, and mounting directions.
- Motorcycle model, connector/protocol, and verified fields including turn signals.
- IMU/GPS placement, coordinate frames, and timestamp alignment.
- How head movement is distinguished from bike movement for zones and event rules.
- Actual pose access, calibration, and display readability through the glasses.
- Alert performance and data-freshness limits measured on the assembled rig.

The [generation prompts and correction edits](motorcycle-prompts.json) record the
built-in imagegen workflow used for the two revised concepts.
