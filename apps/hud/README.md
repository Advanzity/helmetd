# Mac test sender

The first runnable HUD component generates a moving ball, frame counter, and
stream timestamp. It uses the VideoToolbox hardware HEVC encoder and either
records an MP4 or sends H.265 RTP/UDP. The counter identifies generated frames;
gaps can expose dropped frames. Stream time is not a latency measurement.

## Build on macOS

From the repository root:

```sh
brew install cmake ninja pkgconf gstreamer
cmake --preset mac-debug
cmake --build --preset mac-debug
ctest --preset mac-debug
```

The integration test needs Python 3 and the Mac hardware encoder/decoder. It
sends 90 generated frames over local UDP and requires the receiver to decode
30 frames before ending successfully. It does not measure Wi-Fi or Pi latency.

Development environment: Apple M4, macOS 15.6.1, AppleClang 17, GStreamer 1.28.7
(Homebrew formula 1.28.7_2), Ninja 1.13.2. First-time Homebrew GStreamer plugin
scanning can emit warnings from unrelated Python/GTK plugins; required media
elements must still load and the integration test must pass.

Verified on this environment: a 90-frame 1280x720/30 HEVC recording decoded in
full, plus the CTest RTP/UDP loopback with hardware decoding. The receiver uses
explicit Annex B access-unit caps before parsing and system-memory NV12 after
decoding; these avoid the format-negotiation and headless GL issues encountered
with unconstrained caps.

## Local check while the Pi is being prepared

```sh
mkdir -p artifacts
./build/mac-debug/bin/helmetd-test-sender --output artifacts/test.mp4 --frames 150
gst-play-1.0 artifacts/test.mp4
```

The file is finalized at the frame limit or on Ctrl-C. Existing output files are
refused; choose a new filename for another run. Hardware encoding is required,
and a missing encoder is an error rather than a silent software fallback.

## Send to the Pi

```sh
./build/mac-debug/bin/helmetd-test-sender --host helmetd-pi.local --port 5000
```

Defaults are 1280x720, 30 fps, 4000 kbps, RTP payload 96, and a 90000 Hz RTP
clock. Use `--help` for frame size/rate, bitrate, and finite-run options. Raw
encoder input queues are bounded; HEVC uses no frame reordering and requests a
keyframe every second with VPS/SPS/PPS sent with each IDR.

The receiver must use matching RTP caps:

```text
application/x-rtp,media=video,encoding-name=H265,payload=96,clock-rate=90000
```

This is a bench sender using RTP/UDP. It has no RTCP feedback, adaptation,
authentication, remote receipt acknowledgement, or world tracking yet. Successful
sending does not prove the Pi received or displayed frames. The Pi decoder,
adapter, and glasses still require a hardware test.

## Local live receiver (second terminal)

Start this first, then send to `--host 127.0.0.1`:

```sh
gst-launch-1.0 -e udpsrc port=5000 caps="application/x-rtp,media=video,encoding-name=H265,payload=96,clock-rate=90000" ! rtpjitterbuffer latency=20 drop-on-latency=true ! rtph265depay ! video/x-h265,stream-format=byte-stream,alignment=au ! h265parse ! vtdec_hw ! video/x-raw,format=NV12 ! videoconvert ! autovideosink sync=false
```

The 20 ms jitter budget is a starting point for experiments, not a verified
Wi-Fi latency setting. Press Ctrl-C in each terminal to stop.
