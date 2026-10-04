# helmetd

## Helmet MVP

Start the Mac HUD and local navigation/voice console with:

```sh
sh tools/helmet.sh --pi 172.20.10.10
```

Use the verified address for your Pi. Open <http://127.0.0.1:8016> in Zen or
Chrome, enable location, choose a destination, preview the route, and start
guidance. The native HUD receives a north-up route outline, current-position
marker, next turn, and distance. This is a compact route overview; the detailed
street/terrain map remains in the browser. Without a route, the HUD asks for a
destination. Stale location removes the position marker and suspends turns.

Three current camera feeds run independently. Selecting Front/Left/Right/Rear
focuses that view; a missing camera shows unavailable. Rear is reserved for the
fourth camera. Video no longer waits for object detection. Scene advisories
expire independently; spatial boxes are drawn only on their exact source image.
The normal HUD shows camera health, not invented speed or gear. `--demo` enables
simulated telemetry and keyboard fault injection for development.

The launcher reuses running services and both processes survive terminal closure.
Pi camera/display services start independently of SSH. The console automatically
refreshes its local control token after a backend restart. Use **Test voice** to
check the chosen Mac audio output; browser location and microphone are opt-in.

Current hardware limitations: no motorcycle telemetry/indicator input, no fourth
camera yet, and no calibrated world anchoring. Camera placement and headphone
routing need checking on the assembled helmet. The loop requires both devices on
a reachable LAN; changing networks requires updating the Pi's Mac destination.


A monorepo for a wearable, world-anchored HUD using a Raspberry Pi 5, a MacBook,
and XREAL 1S glasses.

Status: the native Metal HUD, Mac test sender, and Python voice/LLM sidecar are implemented.
Mac OpenCV detection adds person/vehicle boxes and image-based caution cues;
see [perception setup](apps/compute/README.md).
The existing Shelby Ride game is imported in `apps/game`; its HUD adapter is pending.
The Pi hardware HEVC receiver and fullscreen display are verified, with a user
service to keep the receiver running independently of SSH. The private ElevenLabs
agent's greeting/audio session and local detection-to-voice bridge have bench checks.
USB camera capture and the OpenCV video loop have a short bench check. Tracking and
world-anchored rendering are pending. See the [stack](docs/stack.md).

Explore the [motorcycle HUD concepts](docs/design/hud/README.md) and
[feature brief](docs/design/hud/feature-brief.md), including normal riding and
signal-driven blind-spot views.

```text
cameras / sensors
       |
       v
Raspberry Pi 5 -- camera + sensor / pose data over Wi-Fi --> MacBook
       ^                                                    |
       |                                           tracking + scene
       |                                                    |
       +---------- rendered HUD video over Wi-Fi -------- renderer
       |
       v
decode + display --> HDMI-to-USB-C adapter --> XREAL 1S
```

The Pi shown on both sides of the loop is assumed to be the same device.
The MacBook owns the scene and HUD rendering. The Pi owns acquisition and
display output. World anchoring requires a verified tracking and calibration
path in addition to the video loop.

## Projects

One Git repository contains the native Mac HUD, Pi media tools, Mac perception
component, Python voice app, and browser-based motorcycle game. The Pi tools
use Python/GStreamer for bench bring-up; sustained camera performance still
needs validation beyond the short USB-camera check.

```text
apps/
  game/                Shelby Ride: simulated motorcycle, traffic, and road world
  capture/             Pi camera/test-source uplink; physical cameras pending
  compute/             Mac OpenCV person/vehicle detection; world tracking pending
  hud/                 Mac: native Metal HUD, camera inset, and HEVC streaming
  display/             Pi hardware HEVC reception and fullscreen Wayland output
  voice/               Mac: ElevenLabs conversation, alerts, and LLM gateway
packages/
  llm/                 OpenAI, Google Gemini, and Anthropic Claude adapters
  protocol/            Shared wire contracts and coordinate conventions
    schemas/
    examples/
config/
  pi/                  Pi configuration examples
  mac/                 Mac configuration examples
hardware/
  calibration/         Calibration procedure and versioned profile definitions
docs/
  architecture.md      Responsibilities, data flow, and open decisions
  repository-plan.md   Proposed project boundaries and creation order
  stack.md             Recommended languages, libraries, and build tools
  roadmap.md           Ordered milestones with acceptance criteria
tools/                 Future setup, replay, and measurement utilities
```

## Run the motorcycle game

```sh
npm --prefix apps/game ci
npm --prefix apps/game run dev -- --port 5173
```

Open `http://127.0.0.1:5173`. See the [game README](apps/game/README.md) for
controls and assets, and the [demo integration plan](docs/game-integration.md)
for connecting gameplay, live cameras, and scripted features to the HUD.

## Build and try the native Mac HUD

```sh
brew install cmake ninja pkgconf gstreamer opencv
cmake --preset mac-debug
cmake --build --preset mac-debug
ctest --preset mac-debug
open build/mac-debug/bin/Helmetd.app
```

The preview has simulated speed/gear, one camera inset, and a triggered rear
warning. Use Space for the warning, arrows for speed, G for gear, C to stall the
camera, and T to stall telemetry. The test camera is a moving ball, not a real
camera capture. The center remains black for the optical HUD background.

See the [HUD README](apps/hud/README.md) for H.264 camera input, recording,
HEVC streaming to the Pi, local checks, and current limits. Generated media and
build output are ignored by Git. Pi hardware decoding and fullscreen output
are verified; optical latency and world anchoring remain untested. See the
[Pi receiver](apps/display/README.md) for persistent display setup.

## Voice and selectable AI providers

The bench uses a private ElevenLabs-hosted agent with Veda Sky. The Helmetd copilot
adds HUD controls, fresh scene descriptions, system checks, ride timing and notes.
Run `sh tools/copilot.sh` to launch HUD and voice together; see the voice guide for
the current cloud-sync status. An optional
Helmetd gateway supports explicit provider selection without renderer changes.

```sh
uv sync --locked
cp -n .env.example .env
# Fill in the chosen provider's key/model in .env, then:
uv run helmetd-llm "Hello" --provider openai
uv run pytest
```

See [voice setup](apps/voice/README.md) for live conversation, spoken alerts,
Mac audio dependencies, and the optional authenticated cloud-to-Mac gateway.
See [the LLM package](packages/llm/README.md) for provider settings.

## Shared road hazards

[Solana devnet road reports](apps/hazards/README.md) let trusted riders publish
expiring hazard observations and retrieve nearby reports without a Helmetd server.
The CLI signs reports, verifies retrieved transactions, filters by distance and
expiry, and supports clear observations. Voice tools use a fresh local GPS/demo
position. GPS hardware and automatic route matching are not connected; publishing
requires a funded devnet wallet.

Start with the [repository plan](docs/repository-plan.md),
[architecture](docs/architecture.md), and
[roadmap](docs/roadmap.md). Hardware facts and unanswered equipment questions
are recorded in [hardware](hardware/README.md).

## Working approach

- Define projects by responsibility and build/run needs. Multiple projects can
  run on one computer; see the proposed boundaries in the repository plan.
- Share protocol contracts first. Keep device-specific implementation in its app.
- Validate the recommended stack with the tracking and display experiments.
- Build hackathon features from gameplay and scripted events; validate physical
  world anchoring as a separate capability.
- Keep captured media and machine-specific configuration out of Git.
