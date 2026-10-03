# helmetd

A monorepo for a wearable, world-anchored HUD using a Raspberry Pi 5, a MacBook,
and XREAL 1S glasses.

Status: the native Metal HUD, Mac test sender, and Python voice/LLM sidecar are implemented.
Voice has offline tests; live cloud/audio setup is pending. Pi applications,
tracking, and world-anchored rendering are pending. See the [stack](docs/stack.md).

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

One Git repository contains four native core projects plus the Python voice app.
The HUD preview/streamer and voice/LLM commands are runnable; capture, compute, and
display document planned responsibilities.

```text
apps/
  capture/             Planned: Pi camera/sensor acquisition and uplink
  compute/             Planned: Mac tracking, anchors, and application state
  hud/                 Mac: native Metal HUD, camera inset, and HEVC streaming
  display/             Planned: Pi stream reception, decoding, and HDMI output
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

## Build and try the native Mac HUD

```sh
brew install cmake ninja pkgconf gstreamer
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
build output are ignored by Git. The Pi/glasses and world anchoring remain untested.

## Voice and selectable AI providers

Helmetd owns reasoning; ElevenLabs handles speech and conversational turn taking.
The provider is selectable through configuration, with no renderer changes.

```sh
uv sync --locked
cp -n .env.example .env
# Fill in the chosen provider's key/model in .env, then:
uv run helmetd-llm "Hello" --provider openai
uv run pytest
```

See [voice setup](apps/voice/README.md) for live conversation, spoken alerts,
Mac audio dependencies, and the authenticated cloud-to-Mac endpoint required
by ElevenLabs. See [the LLM package](packages/llm/README.md) for provider settings.

Start with the [repository plan](docs/repository-plan.md),
[architecture](docs/architecture.md), and
[roadmap](docs/roadmap.md). Hardware facts and unanswered equipment questions
are recorded in [hardware](hardware/README.md).

## Working approach

- Define projects by responsibility and build/run needs. Multiple projects can
  run on one computer; see the proposed boundaries in the repository plan.
- Share protocol contracts first. Keep device-specific implementation in its app.
- Validate the recommended stack with the tracking and display experiments.
- Prove one physical anchor before adding object recognition or a large HUD.
- Keep captured media and machine-specific configuration out of Git.
