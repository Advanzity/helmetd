# 3D navigation map concepts

## Nearby MVP — 2026-10-03

The console at `http://127.0.0.1:8016/` now uses real browser location, nearby OSM
places and Valhalla motorcycle routes. The default 3D view uses MapLibre globe projection, Mapterhorn terrain and
OpenFreeMap building extrusions. Earth imagery comes from USGS; Streets imagery
comes from OpenStreetMap. These are simplified buildings, not photogrammetry.
Tilt/rotate/globe/route camera controls preserve the navigation state. A 2D
Leaflet view remains available and is used when 3D graphics cannot initialize. The native HUD receives the same next turn and
distance. Camera perception does not determine navigation instructions.

The visual direction is a dark workspace with cyan controls, a large holographic
3D map, and a narrow route inspector. Holo uses real road/building geometry with
a geographic grid, translucent extrusions and glowing routes; Earth and Streets
remain available. Ground relief changes the actual elevation mesh (1× true scale,
3× default or 6× exaggerated). A low-angle Terrain view reveals the surrounding
land, and the center elevation readout stays unscaled. High-detail zoom-15 DEM
tiles fall back to zoom-12 global coverage on failure. No camera movement changes navigation state. Numbered map markers correspond to the
nearby results. Preview geometry is dashed and subtly animated; accepted geometry
is solid. Map enlargement and recentering preserve the route. Reduced-motion
preferences remove decorative transitions and route animation.

Implemented: location permission/accuracy, category and named-place search,
preview/start, local-road preference, one added/removed stop, pause/resume, cancel,
manual reroute, off-route detection, stale-location suspension and arrival.
Existing active navigation is preserved until a new preview is accepted. Exact
coordinates stay out of voice context and aren't saved to disk. The console,
its voice conversation and native HUD share route state. End conversation and
cancel navigation are separate actions. The standalone Python voice process has
its own in-memory state; use the browser for this integrated location experience.

Implemented in the browser: automatic Mac-voice turn cues with audio priority,
repeat/reroute announcements, expiring lane-aware hazard reports, confirmed devnet
sharing and upcoming-route hazard warnings.

Remaining: phone/Pi GPS input,
measured road testing, traffic-aware estimates and production map hosting.
Glasses/world-anchored rendering and photorealistic building meshes remain later work.

See [voice setup](../../../apps/voice/README.md) for provider details, controls and
privacy. Main implementation: `nearby.py`, `maps.py`, `web_test.py`, `nearby.js`,
`nearby.css`, `earth-map.js`, and the native `nav_live` control message. The older fictional road
engine remains available for deterministic bench tests.

## Earlier visual concepts

Two additional directions for the motorcycle HUD, generated with built-in imagegen.
These PNGs are visual concepts, not interactive maps, 3D model assets, or a working
routing service. Streets, buildings, routes, timings, and reports are illustrative.

## Compact map

![Compact 3D HUD map](ride-3d-minimap-v1.png)

A small perspective map shows nearby street geometry, the selected route, current
position, trip time/distance, and a reported hazard. The next-turn arrow remains
the primary navigation cue; the miniature map is optional supporting context.
Buildings are simplified and labels sparse so the route is the clearest element.

Proposed behavior:

- Collapse the map when a camera inset or higher-priority alert needs its space.
- Keep the forward road and fixed speed/gear readouts free of map content.
- Use a consistent heading-up orientation; handle stationary/uncertain heading
  explicitly instead of letting the map spin with noisy inputs.
- Adapt map extent near a maneuver with a stable transition rather than abrupt zooms.
- Distinguish reported hazards and group location markers from camera detections.
- Show unavailable or stale location explicitly; preserve the distinction between
  a cached map and a current position fix.

## Expanded route overview

![Expanded 3D route overview](ride-3d-overview-v1.png)

A stationary planning view expands the geometry, destination, route alternatives,
reported hazards, and a group-position dot. Route choices compare estimated travel
time and known report counts. Fewer reports is not a promise of greater safety;
coverage, freshness, and confidence must be part of the eventual comparison.

This is a proposed stopped-only mode, entered through an explicit command/control.
Movement or unavailable movement state should collapse it back to ordinary HUD
navigation. The concept shows route-selection styling, not touch input through
the glasses. Voice and physical control mappings remain implementation work.

## Relationship to world anchoring

The map contains 3D geometry inside a fixed HUD element. It can be prototyped as
ordinary rendered HUD content without claiming that its streets line up with the
physical road. World-anchored road arrows remain a separate goal requiring the
calibrated pose/projection pipeline described in the main roadmap.

## First implementation slice

The native C++/Metal HUD now provides the base render/encode path. Prove it on
the Pi and glasses before adding the map. MapLibre Native is a candidate for
the eventual map integration; this document does not commit to its offscreen
texture interoperability or a routing provider.

1. Add a small synthetic street mesh and route line to the HUD simulator.
2. Drive a position marker along a recorded or simulated route; exercise heading,
   turn transitions, lost location, and alert-driven collapse.
3. Add the expanded stationary view using the same route/scene data.
4. Choose and verify map/routing data sources, usage terms, caching, geographic
   coordinates, and renderer integration before replacing the synthetic scene.
5. Check apparent size, label readability, overlap, and render cost through the
   actual glasses; the full-scene artwork is not a calibrated display specification.

Possible later layers include group markers, route progress, elevation/curve
preview, and time-filtered hazard reports. They should share the alert priority
rules rather than produce additional permanent panels.

Exact prompts and the overview text cleanup are saved in
[3d-map-prompts.json](3d-map-prompts.json). The footer belongs to the presentation,
not the runtime HUD. See the [other HUD states](extended-states.md).

## Browser-to-HUD 3D bridge — 2026-10-04

The native HUD now accepts the actual MapLibre canvas (terrain, streets,
building extrusions and route) from the local console. The open 3D view publishes
640×360 BGRA frames at up to 5 fps through an origin/token-guarded loopback API.
Frames are atomically replaced in `.local/hud-map.bgra`; the native renderer
uploads them as a Metal texture. This replaces the earlier flat route outline.
The inset hides during camera selection or an alert. Frames older than two
seconds are hidden, and native navigation freshness is checked independently.

Current limits: the console must remain open in 3D mode with a route selected;
background browser throttling can interrupt the map. The inset mirrors the
console camera, including its tilt and zoom. Position is drawn only for a usable
fix. This is a fixed HUD map, not stereo or world-anchored road graphics.
Provider credits are included in the frame. Browser DOM search/hazard markers
are not included in the WebGL canvas capture. The last map frame is stored
locally until replaced; it is not a recording history.

The ride view now defaults to zoom 17.2 with a 65° pitch, oriented along the
initial route segment (not measured vehicle heading). The Route control retains
the full-trip overview. Building color varies by mapped height under directional
lighting; route chevrons and a destination flag are composited into the HUD frame.
The Metal map shader suppresses dark haze and feathers the image edges into black.

Reference HUD composition: brand upper left, incoming-video status and unknown
battery upper right, navigation instruction at top center, map at lower left,
and speed/gear at bottom center. Unconnected telemetry uses dashes. Side-camera
indicators remain compact; opening a camera suppresses the map. Camera insets
fade in over 180 ms and the map over 240 ms; loss of input still hides stale
content immediately. Active signal indicators pulse without blinking out.
Text uses a 2× supersampled grayscale-antialiased atlas with mipmap filtering.


### Independent rendering and ride controls

`tools/helmet.sh` starts a separate `helmetd-map-renderer` WebKit process. It renders the 640×360 map on its own clock, so switching browser tabs does not stop map uploads. Route planning and location permissions still use the console; following requires a fresh location fix. Guidance displays the next maneuver's street when available.

Ride view and Quiet mode are available in the console and through `set_hud_mode`. Quiet mode hides the map and normal speed/gear readout while retaining turn instructions and fresh camera advisories. LEFT/RIGHT detections use independent workers and expire after 500 ms; these are object-in-view advisories, not calibrated blind-spot or lane-clearance estimates.

The launcher enables bounded rolling recording under `.local/recordings/rolling/<port>`. Save footage (or the `save_video` voice tool) copies up to six finalized five-second MP4 segments per camera into a unique `.local/recordings/saved/` folder with a manifest. The active partial segment is excluded; outages can produce gaps or shorter footage. No footage is claimed saved when no completed segments exist. Voice camera selection, repeat navigation, and voice volume controls use their existing tool handlers.

Front-camera advisories do not suppress the route map. Their text has a two-second presentation hold measured from the last positive source frame to absorb brief detector misses. The hold is cleared immediately if camera freshness fails or detection fails; raw detections and AI observations are not extended. Explicit camera selection and Quiet mode retain their existing map visibility behavior.

Directional speech confirms detections for 500 ms, announces each camera/object category once, and rearms after two seconds clear. A four-second global cooldown avoids overlapping announcements. The local console service runs this without a cloud voice session, using the configured Pi audio link. Voice detection-alert mute controls apply to this monitor.

The native Mac preview renders the live front camera behind the HUD in a separate GPU pass. The Pi stream and captured output remain black-backed. This is an uncalibrated view, not world registration. Detector submissions are capped at five per second per camera; the newest pending image replaces older work.
