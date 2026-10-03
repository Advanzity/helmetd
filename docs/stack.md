# Recommended stack

Status: native Metal HUD with camera input and HEVC output, synthetic Mac sender,
and voice/LLM sidecar implemented. Remaining components and the Pi hardware path
are pending. The local Mac reports Apple M4
with 16 GiB RAM; this plan
assumes it is also the intended rendering machine.

| Project / layer | Recommendation |
| --- | --- |
| Pi OS | Raspberry Pi OS Lite, 64-bit |
| Capture on Pi | C++20 + libcamera + GStreamer |
| Compute on Mac | C++20 + OpenCV 4 + Eigen |
| HUD on Mac | C++20 core + Metal; Objective-C++ bridge to Metal/AppKit/CoreText |
| HUD encoding | GStreamer using Apple's VideoToolbox HEVC hardware encoder |
| Display on Pi | C++20 + GStreamer, V4L2 stateless HEVC decoder, DRM/KMS output |
| Shared messages | Protocol Buffers with generated C++ bindings |
| Build and checks | CMake presets + Ninja + CTest; clang-format and clang-tidy |
| Pi process startup | systemd, after the bench applications work |
| Voice on Mac | Python 3.12–3.14 + ElevenLabs SDK; PyAudio/PortAudio for local audio |
| LLM reasoning | Shared Python adapters: OpenAI Responses, Google Gen AI, Anthropic Messages |
| Voice gateway | FastAPI + Uvicorn; authenticated Chat Completions SSE endpoint |
| Python workspace | uv workspace + uv.lock; pytest and Ruff |

The native libraries fit a C++ core and give us direct control over capture,
buffering, tracking, and rendering. The tradeoff is more native rendering work
and a Mac-specific HUD. Keep rendering limited to the product's actual graphics.

The first HUD uses a native Metal render target, a CoreText glyph atlas, one
camera texture, and a black optical background. Its state, media integration,
and frame loop are C++20; Apple APIs are isolated in `metal_renderer.mm`. The
bridge uses the system Objective-C Metal API directly, so no metal-cpp headers
or full Xcode shader compiler are needed. Shaders compile once at startup.
React remains an option for the companion/settings/civic UI outside the glasses
render path. MapLibre Native's macOS/Metal integration remains an experiment
after the basic hardware loop; no map SDK has been added.

The [voice sidecar](../apps/voice/README.md) runs separately from the C++ core.
Helmetd chooses the LLM provider and model; ElevenLabs provides speech. Its cloud
agent calls an authenticated HTTPS route to the Mac gateway. Local microphone and
audio output are implemented; the Pi audio link and automatic HUD alerts remain
future integration. Provider switching takes effect when the gateway restarts.

## Media paths to validate

```text
Pi -> Mac: libcamera -> baseline H.264 encode -> RTP/UDP -> decode -> tracking
Mac -> Pi: Metal -> VideoToolbox HEVC encode -> RTP/UDP -> HEVC decode -> HDMI
```

Pi 5 uses software H.264 encoding and has hardware HEVC decoding. That motivates
different codecs in the two directions. For a USB camera, use the appropriate
V4L2 source and reconsider the uplink codec if the camera encodes internally.

Sources: [Pi camera software](https://www.raspberrypi.com/documentation/computers/camera_software.html),
[Pi 5 specification](https://www.raspberrypi.com/products/raspberry-pi-5/),
[libcamera GStreamer integration](https://libcamera.org/getting-started.html).

The candidate downlink elements are `vtenc_h265_hw`, `rtph265pay`,
`rtph265depay`, `v4l2slh265dec`, and `kmssink`, with parsing/session management
as required. Availability and buffer compatibility on the actual Pi OS remain
unverified. Log actual encoder/decoder selection; do not silently count a
software fallback as passing hardware validation.

The first Metal-to-GStreamer bridge is implemented with GPU completion, a blit
to a shared readback buffer, CPU copies, BGRA appsrc, NV12 conversion, and the
VideoToolbox HEVC encoder. Preview and output use the same rendered texture.
It is deliberately a measurable first bridge, not zero-copy; renderer/readback/
enqueue timings exclude encoding completion and downstream transport/display.
Use real-time encoder settings, disable frame reordering where supported, bound
queues/jitter buffering, and test keyframe recovery after packet loss.

The camera receiver requires baseline/constrained-baseline H.264 (RTP payload
97). The local default-profile experiment produced approximately 295 ms of
pipeline age because the VideoToolbox GStreamer decoder buffered that profile;
baseline avoids its H.264 reorder queue. The 250 ms freshness guard rejected
those delayed frames. The [HUD tests](../apps/hud/README.md) now exercise baseline
input alongside HEVC output and verify that stopped camera frames disappear.
This local pipeline age is not a measurement of sensor-to-display latency.

Sources: [Metal C++](https://developer.apple.com/metal/cpp/),
[VideoToolbox HEVC encoder](https://gstreamer.freedesktop.org/documentation/applemedia/vtenc_h265_hw.html),
[HEVC decoder](https://gstreamer.freedesktop.org/documentation/v4l2codecs/v4l2slh265dec.html),
[DRM/KMS sink](https://gstreamer.freedesktop.org/documentation/kms/index.html).

## Contracts and tracking

- Video: GStreamer RTP/RTCP over UDP on the bench LAN.
- Current pose/sensors: small Protobuf UDP datagrams with sequence numbers,
  acquisition timestamps, validity, and stale/out-of-order rejection.
- Session/configuration: length-prefixed Protobuf over reliable TCP.
- Compute-to-HUD: local Unix-domain socket, with bounded/latest-state delivery.
- Associate render metadata with the exact media frame and session.
- First anchor: OpenCV ArUco detection and calibrated pose estimation from a
  known-size physical marker; Eigen for transforms. Tracking beyond marker
  visibility needs additional work.

Sources: [GStreamer RTP](https://gstreamer.freedesktop.org/documentation/rtp.html),
[Protocol Buffers](https://protobuf.dev/overview/),
[OpenCV marker tracking](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html).

## Precision and reproducibility

World alignment depends on camera-to-eye calibration, accessible pose data,
clock synchronization, pose age, and display timing. The proposed stack does
not assume access to the XREAL SDK through the Pi's HDMI adapter. See
[hardware](../hardware/README.md).

Measure optical motion-to-photon latency and alignment during head rotation and
translation. A 60 Hz renderer's 16.7 ms frame interval is not total latency.
The Wi-Fi/macOS/Linux loop has no hard real-time guarantee. If the loop misses
the agreed spatial target, revisit local correction or rendering placement.

Create one CMake target per core project, with Mac and Pi presets. Build natively
on each machine initially. During bench work use OS-native camera/media packages;
record and pin the tested OS image, toolchain, dependency versions, metal-cpp
revision, and matching Protobuf compiler/runtime before treating builds as
reproducible. The sender README records its current test environment; a complete
dependency lock for both platforms remains future work.

Source: [CMake presets](https://cmake.org/cmake/help/latest/manual/cmake-presets.7.html).

First prove the Mac-to-Pi hardware video path, then run the camera uplink
simultaneously, then prove one marker-aligned graphic through the glasses.
