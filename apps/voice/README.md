# Voice on the Mac

## Navigation and voice on the MacBook

The console uses the MacBook browser's location for **real nearby motorcycle routes**.
Click **Use my location**, allow access, then choose fuel, coffee, food or parking
within 5 km, or search for a named destination within 25 km. Preview the selected
place, then start guidance with a fresh position accurate to 60 m or better.
Location accuracy varies on a Mac; planning allows coarser fixes. Guidance stops
when location is stale, imprecise or off route. Arrival needs two accurate fixes.

**3D Holo** is the default map view: cyan roads, translucent building extrusions,
a geographic grid and glowing route layers. It uses a MapLibre globe, terrain elevations from
Mapterhorn, and simplified OpenStreetMap building extrusions from OpenFreeMap.
**Earth** displays USGS aerial/satellite imagery (detailed U.S. coverage), while
**Streets** shows OpenStreetMap. **Tilt**, **Rotate**, **Globe**, and **Route** change
the camera; Control-drag also rotates/tilts. The crosshair returns to your device
position. **Expand** enlarges the view. The camera never changes location or route
progress. Numbered places match the nearby list; previews are dashed, accepted
routes solid. **Ground relief** changes the elevation mesh: **1×** is true scale,
**3×** (default) and **6×** amplify ground height visually. Building heights are
not scaled. **Terrain view** pulls back and lowers the camera to inspect the
surrounding land. The elevation readout is the unscaled DEM height at the map
center, not the device altitude. Detailed terrain tiles load up to zoom 15, with
a reported fallback to global zoom-12 terrain if detailed coverage fails.

This is real 3D geometry, with simplified buildings rather than photogrammetry;
some building heights are estimated by the map data. Imagery is dated, not live.
Terrain and building coverage/loading are provider-dependent. Flat terrain remains
flat. The **3D / 2D** button switches renderers; failed WebGL or initialization
falls back to Leaflet 2D with an explicit notice. Reduced-motion preferences are
respected. Map view controls work with the last known position; active guidance
still requires a fresh fix.

The first build verifies pinned MapLibre 6.12.0 ES modules, worker, shared code and
CSS, downloaded from the official npm release. The checksums in
`web/maplibre-vendor.json` came from the registry-integrity-verified package.
Vendor code and licenses are served locally; terrain/building tile requests go
directly to their named providers. No API key or location persistence is added.

Photon supplies named-place search, Overpass supplies nearby categories, and
Valhalla/FOSSGIS calculates motorcycle routes. Local-road preference is a penalty,
not guaranteed highway exclusion. Times exclude live traffic; opening hours and
fuel availability are unverified. Public providers are suitable for light MVP
usage, with bounded in-memory caching and serialized requests. Configure
`HELMETD_ROUTING_URL`, `HELMETD_GEOCODER_URL` and `HELMETD_OVERPASS_URL` for other
compatible deployments. Imagery source: [USGS The National Map](https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer).

The browser sends position to the loopback server; search/routing providers get it
when needed, and imagery, terrain and building tile providers see the viewed map area. Exact coordinates and
geometry are excluded from voice tools. Route/location state stays in memory;
location permission is requested explicitly and **Stop sharing** suspends guidance.
Reloading requires refreshing location again. No coordinates go to Solana.

Route preview/start, one added stop, pause/resume, reroute and cancel work without
a microphone or cloud connection. Navigation survives ending a conversation.
The native HUD receives real turn state via `nav_live`; its bench speed/gear still
remain simulated. Starting the first route enables **Spoken guidance**, unless you explicitly muted
it. You can also enable it directly or click **Test voice**. It uses
the Mac system voice independently of ElevenLabs and announces the first instruction,
approach thresholds at 500/100/35 m, reroute changes, pauses, location loss and arrival.
**Repeat turn** or a voice repeat request repeats only the current valid instruction.
Cues stop on stale/imprecise location, uncertain route matching or server disconnect.
Approaching reports near the active route are announced once per route; close turn
cues take priority. Conversation output and microphone input are temporarily muted
during these system cues to avoid overlap/echo, then restored. Spoken guidance
must be enabled again after reloading; keep the browser open. This is a Mac MVP,
not background phone navigation or a road-tested warning system. The older fictional road engine is
retained for bench tests, not used by the default console.

### Road reports

Say **“Report debris in the right lane”** during an ElevenLabs conversation, or
use **Road reports → Save report here**. Debris, pothole, blocked lane and standing
water are supported, with left/center/right/shoulder/unspecified lane. The browser
must have a fresh position (15 seconds, accuracy within 60 m). Approximate location,
lane and time are saved privately in `.local/hazards/reports.sqlite3` (0600); duplicate
reports within a minute and 150 m reuse the original. Local active records are
removed after 15 minutes. Exact location and map geometry stay out of voice tools.

Choose **Share**, or ask to share that report, to publish its approximate location,
lane, observation time and wallet to **Solana devnet** after confirmation. Publishing
does not renew expiry. Public chain history remains after a report expires. Pending
or uncertain submissions are never automatically retried; inspect the transaction
outbox if confirmation fails. No report is published simply by saving locally.

Set `HELMETD_TRUSTED_RIDERS` to up to eight comma-separated rider wallet public keys
in the voice environment. Another rider must trust your public key to receive your
reports. With no list configured, the feed reads your wallet only. It refreshes every
30 seconds and labels outages. Reports appear on both 3D and 2D maps; warnings match
within 100 m of the route and 50–700 m ahead with valid guidance. This coarse match
cannot distinguish opposing carriageways: speech says **reported near your route**,
and the lane is the reporter's observation. There is no global discovery feed.
No reports is not evidence that a road is clear. The CLI's GPS-file tools remain
separate; the integrated browser uses browser location directly.

Each new browser voice connection syncs the agent's current personality and tools
before requesting a call token. If ElevenLabs is unreachable, it reports the
failure and retries on the next explicit connection attempt; local navigation
continues independently.

The browser console uses ElevenLabs WebRTC with echo cancellation, microphone and
speaker selection, live transcripts, typed messages, and explicit Talk/Stop controls.
The original Python PCM connection hit upload backpressure and a WebSocket
keepalive timeout on the bench network. Use the browser for MacBook speaker tests:

```sh
cd apps/voice/web && npm run build && cd ../../..
sh tools/voice.sh web-test
```

Open **http://127.0.0.1:8016**, click **Talk to Helmetd**, and allow microphone access.
The first build downloads the pinned vendor browser bundle and verifies its checksum;
later launches serve it locally. API credentials stay in Python. Short-lived voice
tokens and local controls require the same-origin page and a per-process guard;
the server binds only to loopback. One browser session can control the copilot at
a time; disconnected tabs lose their local session after 12 seconds.

MacBook devices are selected when available. Select a different listed device
before connecting if needed. Camera capture and automatic detection speech are
not part of this voice-only test; those tools report unavailable. HUD actions work
when the native HUD is running with its control socket, for example in another terminal:

```sh
sh tools/copilot.sh --preview --camera none --hud-only
```

Stop closes the voice connection and microphone. Transcripts remain in the tab
until reload; this console does not save them locally. ElevenLabs retention still
follows the private agent's settings.

## Helmetd copilot

The copilot is conversational, curious, and dry-witted, with room to banter and
offer an opinion. Action confirmations stay brief and warnings stay calm. It uses
the selected Veda Sky voice and 21 actions, including nearby search and four
route actions. Start the HUD and voice together
from the repository root:

```sh
sh tools/copilot.sh
# Local visual demo (no Pi downlink):
sh tools/copilot.sh --preview --camera test
```

The default uses the Pi USB camera uplink on port 5002 and the Pi HUD downlink at
172.20.10.5. Quit an older HUD that occupies the camera port first. The launcher
reuses a HUD with an active control socket and shuts down only a HUD it created.
Use `--host IP` if the Pi address changes. `--hud-only` runs local HUD controls
without cloud voice. The rendered indicator shows listening, thinking or speaking
and expires if the voice process stops. Clear mode hides it with the other panels.

| Say | Action |
| --- | --- |
| “Helmetd, suit up” / “Let's ride” | Open the full HUD, hide diagnostics, enable spoken alerts, start the ride timer, and report actual readiness |
| “Keep me focused on the road” | Focus HUD, hide diagnostics, and enable spoken alerts |
| “Give me a situation report” | Prioritize system gaps, fresh scene observations, and ride state |
| “What just happened?” | Recall recent sampled camera/HUD observations |
| “We're done. Stand down” | Save the ride summary, clear every HUD panel, and debrief while the microphone stays active |
| “Helmetd, run a system check” | Read camera, detection, HUD, location and voice state |
| “What can you see?” | Summarize fresh detections and their regions in the image |
| “Switch to focus mode” | Keep the telemetry/alerts panel and clear the other panels |
| “Show the camera” / “Hide navigation” | Change panel visibility while detection continues |
| “Show diagnostics” | Toggle the technical display |
| “Set your volume to fifty percent” | Adjust assistant and alert playback volume |
| “Mute detection announcements” / “Turn alerts back on” | Control spoken detection cues |
| “Start my ride” / “End my ride” | Time the session and save its note count |
| “Remember to check the rear tyre” / “Read my notes” | Save requested notes locally and recall the last five |
| “Any road hazards nearby?” / “Report debris here” | Use the Solana hazard tools with a fresh location |
| “Stop listening” | Close the microphone and end the voice session |

You can talk naturally during an active conversation; saying “Helmetd” is optional.
There is no always-on wake-word detector. Start a new conversation after stopping it. Ride
timing is not GPS tracking; it does not invent speed or distance. Notes and ride
summaries are saved privately under `.local/copilot/`; ordinary conversations are
not automatically saved as notes. Requested note recall sends those notes through
the active ElevenLabs conversation.

The copilot keeps a small memory of camera/HUD state changes during the session:
at most 40 changes within two minutes, with the latest eight available for recall.
These are sampled object labels/counts and image regions, not unique people,
distances, a complete history, or recorded video. This memory is not saved to disk.
During an active conversation, compact detection and system metadata is sent as
[non-interrupting background context](https://elevenlabs.io/docs/eleven-agents/customization/events/client-to-server-events)
to ElevenLabs and its configured reasoning provider. No frames, coordinates or
saved notes are included in this background feed. Changes are coalesced to at most
one update per five seconds, with unchanged state refreshed every 30 seconds.
Stale detections are omitted; current scene questions still call the live tool.
The network sender runs separately from HUD updates and detection alerts.

Routines report partial failures instead of claiming every system is online. They
preserve playback volume, never publish a hazard, and leave the detector running.
Stand down hides visual warnings along with every other panel; it keeps the
existing spoken-alert setting. “Stop listening” ends the voice session separately.
The debrief reports elapsed time and saved-note count, with only the limited recent
observations above; it does not claim to reconstruct the entire ride.

At startup, the voice CLI syncs the personality/tools and verifies the result,
preserving the selected voice, model and authentication. Unchanged settings are
not republished. The API payload is also written without credentials to
`.local/copilot/agent-config.json`. `sh tools/voice.sh configure-agent` syncs it
without opening the microphone; `talk --no-sync` explicitly uses the existing
cloud configuration. A running conversation needs to be restarted to pick up a
new personality.

The HUD control interface is an optional mode-0600 Unix socket enabled by
`--control-socket .local/hud-control.sock`. It accepts a fixed set of display/status
commands, not shell commands. The voice layer reports success only after a matching
HUD response. Stale detections are omitted rather than described as current. Replayed
tool-call IDs do not create duplicate notes/reports. A local debug command needs no
cloud connection:

```sh
sh tools/voice.sh act set_hud_mode --args '{"mode":"focus"}'
sh tools/voice.sh act system_check
sh tools/voice.sh actions
```

Python sidecar for a live ElevenLabs conversational agent, cached detection
alerts, and an optional HTTP bridge to Helmetd's own LLM layer. Voice networking runs
outside the native tracking and rendering loop.

```text
Mac microphone -> private ElevenLabs agent + hosted LLM -> Mac output
Native HUD -> localhost UDP -> cached ElevenLabs alert WAV -> Mac output
Agent client tools -> local Solana hazard reader/reporter

Optional Custom LLM: ElevenLabs -> authenticated Helmetd gateway -> packages/llm
```

The current bench agent uses ElevenLabs-hosted Gemini 3.5 Flash, with Veda Sky
(`XcXEQzuLXRU9RcfWzEJt`) and English Flash v2 speech. Standalone alert generation
uses Flash v2.5. A separate provider key or public gateway is not required for
this hosted mode. The optional custom gateway below retains provider selection.
Conversation content goes to ElevenLabs and its configured reasoning provider.
Audio uses the Mac's default microphone/output; Pi microphone and glasses audio
routing are pending.

Microphone upload uses a bounded queue. If scheduling or a connection stall fills
it, the oldest buffered chunks are dropped to preserve recent speech instead of
terminating the session. The terminal reports this recovery; a few words can be
lost during the stall. Actual device failures still stop capture and show a
specific error.

## Current bench launch

The ignored `.local/elevenlabs.env` holds the private agent and voice configuration
(mode 0600). `tools/voice.sh` selects it when present, otherwise `.env`:

```sh
sh tools/voice.sh doctor
sh tools/voice.sh                 # voice + alerts; HUD must already have control enabled
sh tools/voice.sh alerts          # detection alerts only; microphone stays closed
sh tools/voice.sh talk --seconds 15
sh tools/voice.sh talk --macbook   # built-in mic + speakers, even with XREAL attached
```

The private agent was created and its greeting/audio session verified on
2026-10-03. No voice session is started automatically by opening the project.
For another account, set its API key/voice/model locally, then explicitly create:

```sh
uv run helmetd-voice setup-agent --model gemini-3.5-flash
```

This saves the new ID immediately and refuses to create another named Helmetd
when it finds an existing one. Required key permissions are text-to-speech,
Voices Read, and ElevenAgents/Conversational AI Read + Write. The agent requires
authentication and has voice recording disabled; this does not imply zero
transcript retention.

## Automatic detection speech

Add `--voice-port 8014` to the native HUD's existing detection command:

```sh
build/mac-debug/bin/helmetd-hud --camera udp --camera-port 5002 \
  --detect-model .local/models/object_detection_yolox_2022nov.onnx \
  --voice-port 8014 --host 172.20.10.5
```

`prepare-alerts` generates two fixed phrases once into `.local/voice/`, keyed by
voice/model/text. The listener then plays those WAVs locally, with no cloud call
per detection. A cue requires fresh OpenCV state; synthetic Space-key warnings
are not published. The loopback-only UDP protocol carries version, session,
sequence, kind, send time and expiry. Its maximum age is the original frame's
500 ms budget, not a new 500 ms budget per send. Nothing is queued for later.

The listener rejects malformed, expired and replayed packets, announces each kind
once until the scene has been clear for two seconds, and enforces an eight-second
cooldown. Stale/cleared cues cancel pending alert audio. Local alerts interrupt
conversation speech; incoming agent speech is suppressed during the clip and the
microphone sends silence during alert playback. Normal conversational echo
cancellation is not implemented; headphones are preferable for conversation.
Use one HUD publisher and one voice listener. UDP failure never blocks rendering.

## Solana hazard tools

`sh tools/voice.sh configure-agent` attaches `nearby_hazards` and `report_hazard` to
the private agent. `talk` registers their local handlers; no incoming HTTP port
or tunnel is required. See the [shared hazard setup](../hazards/README.md) for
trusted riders, public report contents, devnet funding and fresh GPS/demo position
requirements. GPS is not connected on this bench. These tools are separate from
the person/vehicle detector and are available only after the cloud agent update
succeeds.

Bench status on 2026-10-03: agent creation, greeting/audio, cached speech and the
OpenCV-to-voice UDP gate passed. The initial hazard-tool attachment hit an
ElevenLabs TLS connection reset; the full 16-action agent configuration was later
synced and verified after connectivity recovered. Devnet publishing awaits test SOL;
offline signature and filtering checks pass.

## Setup

Run from the repository root with Python 3.12–3.14 and `uv` available:

```sh
brew install uv portaudio
uv sync --locked --extra audio
cp -n .env.example .env
uv run helmetd-voice doctor
```

Edit `.env` locally. Set the selected provider's key and model ID, plus the
ElevenLabs values needed for your command. No models are selected implicitly:
use an ID enabled in your provider account. The committed `uv.lock` pins SDKs.
Environment variables take precedence over `.env`; `--env-file PATH` selects
another file. `doctor` reports presence only and never prints credentials.
Microphone permission must be enabled for the terminal/app launching `talk`.

## Select and test the reasoning provider

Set `HELMETD_LLM_PROVIDER` to `openai`, `google`, or `anthropic`. The matching
`OPENAI_MODEL`, `GOOGLE_MODEL`, or `ANTHROPIC_MODEL` supplies the model ID.
Only the selected provider's API key is required. A command override leaves the
saved default unchanged:

```sh
uv run helmetd-llm "Say that the camera is ready." --provider openai
uv run helmetd-llm "Say that the camera is ready." --provider google
uv run helmetd-llm "Say that the camera is ready." --provider anthropic
```

See [the LLM package](../../packages/llm/README.md) for its shared interface.

## Optional custom LLM gateway

1. Generate a gateway token with
   `uv run python -c 'import secrets; print(secrets.token_urlsafe(32))'` and save it
   as `HELMETD_GATEWAY_TOKEN` in `.env`.
2. Start `uv run helmetd-voice serve`. It binds to `127.0.0.1:8013` by default.
   `GET /healthz` checks the process; it does not validate provider access.
3. Provide an HTTPS reverse proxy or tunnel to this local port. ElevenLabs runs
   in the cloud and cannot reach `localhost` on the Mac. Tunnel deployment is
   not included. Keep bearer authentication enabled and use a stable URL for
   the agent. The gateway is a single-user bench service, not a multi-tenant API.
4. Create/configure a **private** ElevenLabs agent. Select **Custom LLM**, the
   **Chat Completions** format, and model ID **`helmetd`**. Configure the base URL
   so requests arrive at `https://YOUR-HOST/v1/chat/completions` (normally enter
   `https://YOUR-HOST/v1` when the dashboard appends `/chat/completions`). Store
   the gateway token in the agent's Custom LLM API-key secret; requests must
   carry `Authorization: Bearer <HELMETD_GATEWAY_TOKEN>`.
5. Set the agent's output token limit to **512** to match the default gateway
   maximum, or change both together. Use a text model that supports the agent's
   temperature setting (0–1). Some reasoning models reject temperature; omit it
   in the caller when supported, or select a compatible model.
6. Configure a separate agent's prompt, first message, language, and voice. Disable
   function/system tools, reasoning summaries, and structured/multimodal output
   for this first text-only bridge (including the Solana tools). Nonempty tool lists and unsupported message
   types are rejected explicitly.
7. Save its ID as `ELEVENLABS_AGENT_ID`; set `ELEVENLABS_API_KEY` locally. Start:

```sh
uv run --extra audio helmetd-voice talk
```

Keep `serve` running in a separate terminal. Press Ctrl-C to end the conversation.
`talk` uses the agent's published configuration; it does not edit it. To switch
the live agent to Claude, for example, restart the gateway with:

```sh
uv run helmetd-voice serve --provider anthropic
```

The endpoint and agent model alias remain `helmetd`. Provider selection is fixed
for the gateway process and changes after restart. There is no automatic fallback
to another vendor. No paid API request is made merely by starting the gateway.

## Standalone speech

Set `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, and `ELEVENLABS_TTS_MODEL` to your
chosen voice and a TTS model that supports `pcm_16000` output. An agent ID and LLM
credentials are not required for standalone alerts.

```sh
uv run --extra audio helmetd-voice say "Camera connected. HUD ready."
mkdir -p artifacts
uv run helmetd-voice say "Tracking lost." --output artifacts/tracking-lost.wav
```

WAV export needs no audio device or PyAudio. Output is 16 kHz, mono, signed
16-bit PCM. Existing files are never overwritten; interrupted exports are
removed. The live session's voice is configured separately in the agent.

## Verification

```sh
uv run pytest
uv run ruff check apps/voice packages/llm
uv run ruff format --check apps/voice packages/llm
```

Offline tests exercise the actual provider SDKs against simulated HTTP/SSE,
provider selection, request validation, auth, errors, stream cancellation,
ElevenLabs PCM/WAV handling, and audio cleanup. They do not verify billing,
credentials, account model access, microphone permissions, speech latency, or
the cloud-to-Mac route. After configuration, run one text prompt, one saved alert,
and a short live conversation; interrupt speech and confirm audio stops cleanly.

References: [ElevenLabs Python SDK](https://elevenlabs.io/docs/eleven-agents/libraries/python),
[Custom LLM integration](https://elevenlabs.io/docs/eleven-agents/customization/llm/custom-llm),
[streaming TTS](https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/streaming).


### Camera-aware copilot

The hosted copilot can call `inspect_camera` for front, left, right, rear, or all views. The native HUD runs local YOLOX inference on configured camera streams and returns at most ten person/road-vehicle detections per camera. A result expires 500 ms after its source frame; missing cameras are unavailable, never treated as clear. `describe_scene` aggregates available views. Background context contains bounded metadata, not pixels or coordinates. This does not support arbitrary image questions, sign reading, range measurement, or lane-change approval.

Supported requests include “what's in the left camera?”, “show rear”, “repeat the next turn”, “quiet mode”, and “save the last 30 seconds”. Saved video is finalized local segments, possibly shorter than 30 seconds. Voice volume controls conversation playback separately from the browser's Spoken guidance setting.

After changing tools or the agent prompt, run `sh tools/voice.sh configure-agent`, then start a new conversation in the local console. A network failure leaves the configuration saved locally but does not update the hosted agent. Camera inference and local controls do not require the conversational cloud connection.
