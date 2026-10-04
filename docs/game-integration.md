# Game-driven hackathon demo

Status, 2026-10-03: Shelby Ride is imported under `apps/game`. It runs as an
independent Three.js/Vite application. Connecting its state to helmetd, adding
scenario controls, and driving the physical Pi/glasses loop remain pending.

## Demo scope

Keep the broad feature experience and simulate most sensing and intelligence.
Use the existing cameras for live video and the game for riding state. Manual
or timed triggers supply the features that are not already in gameplay.

The game is the source of simulated riding data; its state is not a measurement
of a physical motorcycle or of objects in the real camera feeds.

| Input / feature | Initial source |
| --- | --- |
| Camera windows | Physical cameras via Pi capture and the Mac receiver. |
| Speed, RPM, gear, throttle, brakes, acceleration, lean | Existing `MotorcyclePhysics` state. |
| Position and heading | Existing game coordinates; geographic conversion is a separate adapter task. |
| Nearby traffic | Game car identities, positions, and speeds; derive relative zones/closing rates for the simulation. |
| Crash | Existing game crash flag or an operator trigger. |
| Rider turn signals | New game controls or operator toggles; currently absent from the motorcycle input code. |
| Navigation, road hazards, near misses | Authored route instructions and scenario events. |
| Group riders, shared hazards, civic reports | Seeded records updated by the same scenario events. |
| Incident recording and emergency packet | Initially an incident record/preview; real synchronized clip capture is separate work. |
| Spatial labels | Can be staged in the rendered game scene using its virtual camera; physical-world registration remains pending. |

Keep input provenance in the operator/debug view. Do not project game vehicle
coordinates onto unrelated real camera images as though they were detections.

## Component placement

Keep the existing monorepo boundaries:

```text
apps/game       Gameplay, simulated vehicle/traffic state, future demo controls
apps/capture    Pi camera and sensor acquisition
apps/compute    Future input adapter, scenario events, alert priority, HUD state
apps/hud        Native Mac HUD and encoded display output
apps/display    Pi reception and glasses output
apps/voice      Existing voice sidecar
packages/protocol  Agreed game/compute/HUD message definitions
```

Game state should leave the browser through a small local bridge into compute.
Choose its browser-compatible transport when implementing the bridge; the
native socket/protocol plan does not itself provide a browser endpoint. Keep
camera video on the existing media path.

Start the adapter at the game loop in `apps/game/src/main.js`, reading
`physics` and `roadTraffic.cars`. Export snapshots at a bounded rate independently
of the physics timestep. Include a session ID, sequence, timestamp, source,
paused state, and reset event. Use meters/seconds for speed and meters/radians
for local position/orientation, documenting the game's axes and heading
convention before mapping them into HUD coordinates. Rendering currently
converts speed to MPH with a factor of 2.23694.

Pause, reset, and reconnect must clear stale alerts. Car IDs can be reused when
traffic respawns, so consumers must not treat an ID as a persistent road user.
Do not compare browser and native timestamps without defining their clocks.

## Build order

1. Run the imported game independently and retain its existing tests.
2. Define a minimal snapshot contract and bridge speed, gear, RPM, and brakes
   into the Mac HUD. Verify pause/reset/reconnect behavior.
3. Add manual scenario controls for signals, blind spots, rear threat, road
   hazard, group updates, incident save, and crash countdown.
4. Drive the HUD and a companion dashboard from the same scenario state.
5. Connect real camera windows and validate Mac-to-Pi-to-XREAL output.
6. Replace individual simulations only where doing so improves the demo.

Demo sequence: cruise → signal left → blind-spot warning → rear threat → road
hazard reported → second rider warned → near miss saved → crash countdown →
dashboard recap. Each step should also be individually triggerable and resettable.

## Run from the monorepo root

```sh
npm --prefix apps/game ci
npm --prefix apps/game run dev -- --port 5173
npm --prefix apps/game test
npm --prefix apps/game run build
```

The game keeps its own lockfile. CMake and uv continue to manage the native and
Python components. Asset authoring is documented in the
[pipeline notes](../apps/game/pipeline/README.md).

## Implemented local bridge (2026-10-04)

Run the helmet console on port 8016 (`sh tools/helmet.sh --pi <Pi IP>`), then
`npm --prefix apps/game run dev` and open `http://127.0.0.1:5173`.
Vite proxies only `/api/game` to the local console; the browser obtains an
origin-guarded action token and sends at most ten snapshots per second, with one
request in flight. The game footer reports HUD acknowledgement, not merely HTTP
connectivity. This bridge is configured for the Vite development server; a
separately hosted production build needs equivalent same-origin proxy routing.

- Z: toggle left signal; V: toggle right signal; X: cancel.
- Speed and gear use motorcycle physics. RPM is carried in the native state.
- Nearby game cars produce left/right, rear, and forward proximity warnings.
  The adapter uses heading-relative positions, ignores other road elevations,
  and holds a warning for one second to avoid boundary flicker. These are
  proximity cues, not estimates of collision probability.
- Collisions use the physics crash flag. The HUD retains a crash message until
  reset with R; it does not contact emergency services.
- Pause/settings/map clear active game cues. Browser disconnection expires
  native game state after 1.5 seconds. Reset changes the session identifier;
  reordered packets and retired sessions are rejected.
- Game cues can speak through the existing Pi audio output. Camera detections
  remain separate; game vehicle positions are never drawn on real camera video.
- Native status exposes `telemetry_source`, `game_fresh`, `game_crashed`, and
  `game_warning_mask` for operator verification. No game input is represented
  as physical motorcycle telemetry.

To check: ride and compare speed/gear, press Z then V then X, approach traffic,
collide and reset with R, pause with P, then close the game tab and confirm the
HUD removes game telemetry/cues. Audio requires the existing Pi audio service.

## Foot reverse and road navigation

Hold **B** while nearly stationary to paddle backward at up to 1.15 m/s
(about 2.6 mph). Releasing B or braking stops the movement; throttle prevents
engaging reverse. The existing rider skeleton plants alternating feet and eases
back to the pegs. Both the game and native HUD show R during backward movement.

Press **M**, leave **Navigate here** selected, and click a road. The route follows
the loaded game road graph, including one-way edges and available turn
restrictions. The game minimap and street map highlight it; a compact instruction
shows the next turn and distance. Guidance follows game position, detects route
deviation, retries routing at a bounded rate, and shows arrival. **End route**
clears it. **Move rider here** retains the original map relocation behavior.

The native HUD receives the same instructions and a simplified route outline
(up to 32 points), using game coordinates rather than phone GPS or the physical
navigation map texture. While game packets are connected, the console's saved
route is not allowed to overwrite game guidance. After disconnection the console
resumes its navigation publisher. Physical display registration is unchanged.

Checks: reverse speed/stop/brake behavior, both leg chains in the shipped GLB,
one-way routing, disconnected roads, turn restrictions, arrival, shipped-map
connectivity, reverse telemetry, and game navigation ownership are covered by tests.
