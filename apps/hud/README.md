# Native Mac HUD

`helmetd-hud` renders a head-fixed 1280x720 HUD with Metal: simulated speed and
gear, one rear-camera inset, and a five-second simulated warning. The same
rendered texture feeds the Mac preview and optional HEVC recording/RTP output.
The camera is a moving test ball by default; it can also receive baseline H.264
over UDP. No Mac webcam or microphone is opened.

This is the first bench implementation. Actual CAN telemetry, detection-driven
warnings, world anchoring, maps, voice integration, and the Pi/glasses test remain
pending. Simulated values are labeled on the HUD. Black pixels are the optical
background, not a camera view of the forward road.

## Build and open

On macOS with Command Line Tools and a Metal-capable GPU:

```sh
brew install cmake ninja pkgconf gstreamer
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
| Space | Trigger/clear a simulated rear-approach warning; expires after 5 seconds |
| Up / Right | Increase simulated speed |
| Down / Left | Decrease simulated speed |
| G | Cycle simulated gears N, 1–6 |
| C | Stall/resume camera updates; the old image disappears after 250 ms |
| T | Stall/resume simulated telemetry; numbers disappear after 1 second |
| Q / Escape | Quit and finalize a recording |

The window title lists controls. The display has no touch interaction assumptions.
Warning onset changes the camera accents to amber, then returns to cyan on expiry.

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

## Send the HUD to the Pi when it is ready

Start a matching Pi receiver first, then use its real hostname or IP:

```sh
./build/mac-debug/bin/helmetd-hud --host helmetd-pi.local --port 5000
```

Downlink: HEVC RTP/UDP, payload 96, 90000 Hz clock. The proposed Pi path remains
`rtph265depay ! h265parse ! v4l2slh265dec ! kmssink`; its plugin availability,
DRM permissions, buffer compatibility, adapter mode, and optical output must be
verified on the actual device. The Pi display service and disconnect watchdog
are not implemented. Successful sending cannot confirm receipt or display.

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
synthetic. It is not an object detector and does not generate real warnings.

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

The frame counter and elapsed monotonic time are drawn into the encoded image.
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
   and a clear center; also output overwrite refusal.
4. Metal HUD -> local RTP -> hardware HEVC decode.
5. Baseline H.264 uplink -> camera texture -> HEVC recording, followed by sender
   shutdown and verification that the old camera image disappears.
6. Unsupported H.264 profile -> camera error, while the HUD continues rendering
   and encoding with the camera unavailable.

The baseline transport tool remains available as `helmetd-test-sender`; see
[its instructions](test-sender.md). Tests were run on Apple M4/macOS 15.6.1,
AppleClang 17 and Homebrew GStreamer 1.28.7. Physical Pi/XREAL validation is pending.

Repeated local runs exposed an intermittent `VTDecompressionSessionCreate
returned -4` startup failure in the original synthetic sender's HEVC loopback.
The new native HUD loopback passed its three repeated runs, and the complete
suite also passed. The intermittent legacy receiver failure is unresolved; do
not interpret a passing local test as proof of sustained hardware reliability.

API references: [Metal shader compilation](https://developer.apple.com/documentation/metal/mtldevice/makelibrary(source:options:)),
[GStreamer appsrc](https://gstreamer.freedesktop.org/documentation/applib/gstappsrc.html),
[GStreamer appsink](https://gstreamer.freedesktop.org/documentation/applib/gstappsink.html),
[GStreamer 1.28.7 VideoToolbox decoder](https://github.com/GStreamer/gstreamer/blob/1.28.7/subprojects/gst-plugins-bad/sys/applemedia/vtdec.c).
