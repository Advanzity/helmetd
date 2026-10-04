# Native Mac HUD

`helmetd-hud` renders a head-fixed 1280x720 HUD with Metal: simulated speed and
gear, one rear-camera inset, a demo navigation cue, and a five-second simulated
warning. Three independent panels sit on a pure-black canvas: camera on the
left, navigation low in the center, speed/gear/alerts on the right. The same
rendered texture feeds the Mac preview and optional HEVC recording/RTP output.
The camera is a moving test ball by default; it can also receive baseline H.264
over UDP. No Mac webcam or microphone is opened.

This is a bench implementation with optional OpenCV image-based caution cues.
Actual CAN telemetry, world anchoring, maps, voice integration, and optical latency testing
remain pending. Pi hardware HEVC decoding and fullscreen Wayland output have
been verified. Simulated values are labeled on the HUD. Black pixels are the optical
background, not a camera view of the forward road.

## Build and open

On macOS with Command Line Tools and a Metal-capable GPU:

```sh
brew install cmake ninja pkgconf gstreamer opencv
cmake --preset mac-debug
cmake --build --preset mac-debug
ctest --preset mac-debug
open build/mac-debug/bin/Helmetd.app
```

Or run `./build/mac-debug/bin/helmetd-hud` for terminal diagnostics. The app
bundle is a local development convenience and uses the installed GStreamer
libraries; it is not a self-contained distribution. Full Xcode is not required:
Metal shaders compile once at startup using the system framework.

| Key | Bench control |
| --- | --- |
| 1 | Show/hide the left camera panel; capture and detection keep running |
| 2 | Show/hide the center demo navigation cue |
| 3 | Show/hide the right speed, gear, and alert panel together |
| D | Show/hide diagnostics; hidden by default |
| Space | Trigger/clear a simulated rear-approach warning; expires after 5 seconds |
| Up / Right | Increase simulated speed |
| Down / Left | Decrease simulated speed |
| G | Cycle simulated gears N, 1–6 |
| C | Stall/resume camera updates; old imagery expires after 250 ms, or 500 ms with detection |
| T | Stall/resume simulated telemetry; numbers disappear after 1 second |
| Q / Escape | Quit and finalize a recording |

The window title lists controls. The display has no touch interaction assumptions.
Warning onset changes the camera accents to amber, then returns to cyan on expiry.
Use these keys with the Mac HUD window focused; Pi keyboard events are not
forwarded to the Mac. The navigation arrow and distance are a static, labeled
demo, with no route or game connection yet. All panels share the same flat
video canvas; they are not separately world-anchored screens.

All three panels start visible. Choose an initial layout with `--panels all`,
`--panels none`, or a comma-separated selection such as `--panels nav,telemetry`.
`--panels none` produces a completely black frame unless `--diagnostics` is
also set. Panel visibility controls drawing, separately from the `C`/`T`
input-stall controls. Hidden panels do not reappear automatically for alerts.

## Record and inspect rendered output

```sh
mkdir -p artifacts
./build/mac-debug/bin/helmetd-hud --headless --warning --frames 150 \
  --output artifacts/hud.mp4 --snapshot artifacts/hud.png
gst-play-1.0 artifacts/hud.mp4
```

`--snapshot` saves the last frame, including when exiting a window normally.
Existing outputs are refused. `--output` defaults to 150 frames and requires a
finite frame count. `--headless` still renders on the GPU; it suppresses the Mac
window. `--camera none` exercises the unavailable-camera state.

`--width`, `--height`, `--fps`, and `--bitrate` configure output. The first layout
requires even 16:9 dimensions from 640x360 to 1920x1080. The default is 720p30,
4000 kbps. See `--help` for every option.

## Keep the HUD on the Pi display

Start a matching Pi receiver first, then use its real hostname or IP:

```sh
open -n build/mac-debug/bin/Helmetd.app --args \
  --host helmetd-pi.local --port 5000 --frames 0
```

Launching the app through macOS keeps it independent of the terminal or chat
command session. `--frames 0` streams continuously until the app is closed.
Keep the Pi receiver under its own process manager too; an interrupted SSH
session must not remove the HUD and expose the desktop. Use the terminal
executable directly for bounded diagnostics and captured metrics.

Downlink: HEVC RTP/UDP, payload 96, 90000 Hz clock. The verified bench Pi path
uses `rtph265depay ! h265parse ! v4l2slh265dec`, followed by explicit conversion
to BGRx/sRGB and `waylandsink` inside the existing desktop session. This avoids
the tested compositor's incorrect color range on direct YUV scanout. The
[Pi receiver and user service](../display/README.md) wait for a keyframe when
joining the stream and retain the last image during receive gaps. That keeps
the demo visible; a retained image is not fresh telemetry. DRM/KMS output and
optical latency remain untested. Successful sending alone cannot confirm receipt.

For a local Mac receiver, start this in a second terminal and send to
`--host 127.0.0.1`:

```sh
gst-launch-1.0 -e udpsrc port=5000 caps="application/x-rtp,media=video,encoding-name=H265,payload=96,clock-rate=90000" ! rtpjitterbuffer latency=20 drop-on-latency=true ! rtph265depay ! video/x-h265,stream-format=byte-stream,alignment=au ! h265parse ! vtdec_hw ! video/x-raw,format=NV12 ! videoconvert ! autovideosink sync=false
```

The Mac hardware decoder has its own buffering; this receiver proves image
transport, not the latency of the proposed Pi hardware decoder.

## Receive one camera

```sh
./build/mac-debug/bin/helmetd-hud --camera udp --camera-port 5002
# Once the Pi receiver also works, combine uplink and downlink:
./build/mac-debug/bin/helmetd-hud --camera udp --camera-port 5002 \
  --host helmetd-pi.local --port 5000
```

Uplink contract: baseline/constrained-baseline H.264, RTP payload 97, 90000 Hz
clock. Start with 640x360 at 30 fps and frequent keyframes/parameter sets. Other
H.264 profiles are rejected: the current GStreamer VideoToolbox decoder buffered
the default-profile bench stream enough to exceed our freshness budget. The Pi
encoder must be configured for baseline; its capture command depends on the
camera and OS setup and remains to be validated.

To exercise this without a Pi, run the HUD with `--camera udp`, then this on the
Mac in another terminal:

```sh
gst-launch-1.0 -e videotestsrc is-live=true pattern=ball ! video/x-raw,width=640,height=360,framerate=30/1 ! videoconvert ! video/x-raw,format=NV12 ! vtenc_h264_hw realtime=true allow-frame-reordering=false max-keyframe-interval=30 ! video/x-h264,profile=baseline ! h264parse ! rtph264pay pt=97 config-interval=-1 ! udpsink host=127.0.0.1 port=5002 sync=false
```

Stop the sender to see the inset switch to unavailable. The receiver keeps only
the newest decoded frame. Freshness is estimated from the local pipeline clock
and PTS, including time spent decoding/queued locally. It does not measure the
remote sensor's acquisition age or include clock synchronization. The inset is
explicitly labeled with source type; a synthetic source sent over RTP is still
synthetic by default. Add `--detect-model .local/models/object_detection_yolox_2022nov.onnx`
to enable OpenCV person/vehicle detection, labeled boxes in the camera inset,
and persistent image-based caution cues. See [perception setup](../compute/README.md)
for the model download, USB-camera command, thresholds, and limitations.

A runtime camera pipeline error is logged and removes the inset while the HUD
continues. Fix the source and restart the HUD after a decoder/negotiation error;
ordinary pauses resume when fresh frames arrive. Reconnect/session recovery,
peer authentication, RTCP, and congestion control remain future work.

## Implementation and timing

- `hud_state.hpp`: simulated input state, warning expiry, freshness budgets.
- `hud_main.cpp`: paced frame loop, controls, media/render coordination, metrics.
- `metal_renderer.mm`: AppKit window, Metal pipeline, CoreText glyph atlas,
  camera texture, render target, and PNG export behind a C++ interface.
- `media.cpp`: latest-frame camera appsink and bounded HEVC appsrc pipeline.
- `hud_options.cpp`: validated command-line configuration.

The initial bridge waits for one GPU frame to complete, blits to shared memory,
copies BGRA into appsrc, converts to NV12, and uses `vtenc_h265_hw`. It is not
zero-copy. The appsrc queue holds at most two frames and drops oldest frames
under backpressure. File output also prioritizes current frames over guaranteed
frame retention. Hardware encoding is explicit; there is no silent fallback.

With `D` or `--diagnostics`, the frame counter and elapsed monotonic time are
drawn into the encoded image.
Exit metrics include rendered/submitted/encoded counts, missed render ticks,
camera sample count/local age, and p50/p95 CPU wall time for render + readback +
enqueue. Those timings exclude encoder completion, Wi-Fi, Pi decoding, and
glasses scanout. They do not establish motion-to-photon latency. The frame loop
skips missed deadlines instead of catching up with a burst of obsolete frames.

Measured validation must next use simultaneous uplink/downlink on the real
Wi-Fi link and an optical timing measurement through the glasses. Pose access,
camera-to-eye calibration, and world anchoring remain separate requirements.

## Checks

CTest exercises the actual local media stack; it does not mock Metal or codecs:

1. Original synthetic sender -> local RTP -> hardware HEVC decode.
2. State expiry, invalid timestamps, warning controls, and option guards.
3. Metal HUD -> HEVC file -> hardware decode, checking warning/text/camera pixels
   and a clear center; also independent panel visibility, exact-black empty
   output/backplates, and output overwrite refusal.
4. Metal HUD -> local RTP -> hardware HEVC decode.
5. Baseline H.264 uplink -> camera texture -> HEVC recording, followed by sender
   shutdown and verification that the old camera image disappears.
6. Unsupported H.264 profile -> camera error, while the HUD continues rendering
   and encoding with the camera unavailable.

The baseline transport tool remains available as `helmetd-test-sender`; see
[its instructions](test-sender.md). Tests were run on Apple M4/macOS 15.6.1,
AppleClang 17 and Homebrew GStreamer 1.28.7. A separate Pi 5 bench test verified
HEVC hardware decode and fullscreen Wayland output. Camera hardware, optical
alignment, and motion-to-photon latency remain unverified.

Repeated local runs exposed an intermittent `VTDecompressionSessionCreate
returned -4` startup failure in the original synthetic sender's HEVC loopback.
The new native HUD loopback passed its three repeated runs, and the complete
suite also passed. The intermittent legacy receiver failure is unresolved; do
not interpret a passing local test as proof of sustained hardware reliability.

API references: [Metal shader compilation](https://developer.apple.com/documentation/metal/mtldevice/makelibrary(source:options:)),
[GStreamer appsrc](https://gstreamer.freedesktop.org/documentation/applib/gstappsrc.html),
[GStreamer appsink](https://gstreamer.freedesktop.org/documentation/applib/gstappsink.html),
[GStreamer 1.28.7 VideoToolbox decoder](https://github.com/GStreamer/gstreamer/blob/1.28.7/subprojects/gst-plugins-bad/sys/applemedia/vtdec.c).

## XREAL optical transparency

The renderer clears every frame to RGB zero. A fullscreen Pi capture of the
earlier layout on 2026-10-03 measured 97.45% exact-black pixels in normal mode
with the synthetic camera. This measures image coverage, not the lenses'
optical transmission.

The three-panel version measured 99.23% exact black in its 1280x720 renderer
snapshot and 98.41% in a 1920x1080 Pi fullscreen capture after HEVC decode and
scaling. Both used the synthetic camera, all panels visible, diagnostics off,
and no warning. Real camera footage and warnings change this coverage.
The six HUD CTest checks passed in `build/mac-panels`; the `1`/`2`/`3`/`D`
controls were also checked in the running Mac app. The Pi receiver remained
active with zero restarts through the sender switch. The verified live app
for this bench run is `build/mac-panels/bin/Helmetd.app`.

For the XREAL 1S, use the clearest electrochromic lens setting and adjust display
brightness to the lowest comfortably readable level. On current One Series
firmware, `+/-` opens the quick panel and `X` selects brightness or electrochromic
dimming. These are separate controls: reducing screen brightness reduces emitted
image light; lens dimming controls the view through the glasses. See the
[official controls guide](https://tutorials.xreal.com/docs/glasses/one-series/quick-guide/)
and [1S specifications](https://tutorials.xreal.com/docs/glasses/one-series/spec/).

The three-panel layout reduces emitted background light:

- Unavailable-camera and warning backplates are pure black; detection labels
  use black masks over footage for readability.
- Diagnostic text is opt-in. Foreground labels use a brighter palette and bold
  glyphs so they remain easier to read with the glasses' display brightness low.
  Primary text is full white; cyan/amber accents retain their status colors.
  This boosts UI pixels only, leaving black and camera footage unchanged.
- The camera inset is smaller and can be hidden with `1`. A real video frame can
  light up most of that rectangle, unlike the mostly black synthetic test feed.
- Speed/gear/alert text stays at the right, leaving the central view clear.
  The demo navigation cue occupies only the lower center and can be hidden.

Changing desktop-window opacity is not part of this path: the Pi receives a
fully composed RGB video stream, so the renderer must produce the desired black
pixels and foreground colors before encoding.

The foreground palette can use more of the available pixel range, but it cannot
exceed the OLED's luminance limit at the selected hardware brightness. Bold
letters increase the visible stroke area, not the maximum brightness of an
individual white pixel. Lens dimming should be adjusted separately from display
brightness; a zero-black screenshot does not establish optical transparency.

## Four camera helmet setup (October 4, 2026)

The current bench uses FRONT on UDP 5002, LEFT on 5004, RIGHT on 5006,
and reserves REAR on 5008. Each feed expires independently; missing images are
replaced by a black unavailable panel. Detection runs on FRONT only.

Quit the existing HUD before starting another sender. From the repository root:

```sh
open -n build/mac-debug/bin/Helmetd.app --args \
  --camera udp --camera-label FRONT --camera-port 5002 \
  --extra-camera LEFT:5004 --extra-camera RIGHT:5006 --extra-camera REAR:5008 \
  --detect-model "$PWD/.local/models/object_detection_yolox_2022nov.onnx" \
  --host BigDaddyD.local --port 5000 \
  --control-socket "$PWD/.local/hud-control.sock" --voice-port 8014 --frames 0
sh tools/voice.sh web-test
```

If mDNS is unavailable, replace `BigDaddyD.local` with the verified Pi address
(current hotspot bench: `172.20.10.10`). The console is at
<http://127.0.0.1:8016>. Closing the console does not stop this separately
launched HUD. Pi services also run independently of SSH.

- `L` / `R`: toggle a demo turn signal and focus that side camera for 15 seconds.
- `B`: toggle rear view; `X`: clear signal and restore automatic front view.
- Console buttons and voice tools `set_turn_signal` / `set_camera_view` offer
  the same controls. Physical motorcycle signals are not connected.
- Navigation: grant location using **Use my location**, search, preview a route,
  and start guidance. Fresh location is required for actual turns. The console
  sends guidance to the native HUD independently of a voice conversation.
- Audio: **Test voice**, **Enable spoken guidance**, and **Repeat turn** use the
  Mac system voice. **Talk to Helmetd** starts the separate ElevenLabs call.
  Spoken route hazards are supported; automatic side-camera blind-spot detection
  is not implemented. Actual helmet speaker routing must be selected and tested.

Three physical cameras and front detection were verified live on October 4.
The fourth camera was absent; REAR correctly remained unavailable. Left/right
assignments follow USB ports and still need checking against physical mounting.


### MVP stability changes

The default display now uses live camera health instead of simulated speed/gear.
Pass `--demo` for the older bench telemetry. Primary video updates at camera
cadence independently of YOLOX completion; scene metadata retains its own source
timestamp and 500 ms expiration. Boxes are never projected onto an unmatched
newer frame. Each video reports delayed after 500 ms. A clearly labeled last frame remains
visible for at most 1500 ms before clearing; it is never counted as live. Failed or stalled receivers retry without restarting the
whole HUD. A feed that has never appeared is omitted from the overview, but can
still be selected explicitly to see its waiting state.

`nav_map` carries up to 32 normalized route points plus a position marker from the
same navigation snapshot as `nav_live`. The native north-up overview preserves
geographic aspect ratio. Preview routes are gray; active routes cyan; stale
positions disappear. Source streets, terrain and buildings are shown only in
the browser. Native map geometry expires after three seconds without updates.

Use `sh tools/helmet.sh --pi <verified-pi-address>` for the combined persistent
startup. The default downlink target is 2500 kbps. On the current hotspot profile,
Pi Wi-Fi power saving was disabled using NetworkManager's `powersave=2` and
`iw dev wlan0 set power_save off`; no Wi-Fi credentials are stored in this repo.

### Minimal glasses view
Live output keeps the center clear: amber camera-relative detection cues at the left/right edges, rear chevrons below, and a front-person marker above compact cyan navigation. These cues do not estimate collision risk or world position. Camera control selections return to auto after eight seconds; signal views retain their existing timeout. Healthy connection chrome and placeholder telemetry are hidden. Quiet mode retains detection cues.

The local control socket accepts `notification APP SENDER` (20/28 characters, letters/numbers/underscore/hyphen/period; underscores display as spaces). It shows only those two fields for three seconds, with no body, suppresses display during detection alerts or quiet mode, and never queues old notifications. A phone or Mac notification-source integration is still required; no notification access is enabled automatically.
