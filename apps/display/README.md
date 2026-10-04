# Pi HUD display

`receive.py` receives the Mac's HEVC RTP/UDP stream, hardware-decodes it with
`v4l2slh265dec`, converts decoded video to full-range BGRx/sRGB, and displays it
through `waylandsink`. Hardware decoding remains on `/dev/video19`; CPU color
conversion ensures RGB zero reaches the existing Wayland desktop. It does not
stop the compositor or claim DRM ownership. Python drives the GStreamer
lifecycle; pixels stay in the native media pipeline.

Do not remove the RGB conversion without checking physical scanout color
properties. The tested labwc path directly scanned limited-range BT.709 NV12
with the plane configured for full-range BT.601, lifting black above zero.
A compositor screenshot could still look black because capture used a different
conversion path. `videoconvert ! video/x-raw,format=BGRx,colorimetry=sRGB`
removes that YUV range/matrix ambiguity before scanout. This costs conversion
work and is not a zero-copy path.

RTP uses UDP 5000, payload 96 and a 90000 Hz clock. The 120 ms jitter budget and
`wait-for-keyframe=true` favor stable demo playback on the current hotspot.
The decoded-frame queue holds at most two frames. The app requests fullscreen
after its first rendered frame, avoiding the sink's early fullscreen warning.
No software decoder fallback is enabled.

## Keep it visible

Use the [systemd user service](../../config/pi/README.md) for a live demo. It
survives SSH/tool-session cancellation and restarts the receiver if it exits.
Launch the Mac HUD as a normal macOS app using the command in the
[HUD README](../hud/README.md). An SSH foreground command is useful for bounded
tests but is not the persistent demo launcher.

```sh
# On the Pi, after installing the user service:
systemctl --user start helmetd-display
systemctl --user status helmetd-display --no-pager
tail -f ~/.local/state/helmetd-display.log

# Deliberately stop it when the demo is over:
systemctl --user stop helmetd-display
```

The demo deliberately **retains the last displayed frame during stream gaps**;
the 500 ms freshness check only logs transitions. It never switches a healthy
display to black. Frozen numbers are not live measurements. The receiver has
no window before the first frame; a process crash/restart can briefly reveal the
desktop. This is bench presentation behavior, not a finished rider safety UI.

## Bounded checks

Do not run a second receiver on the live service's UDP port. Use another port
and `--sink headless` for independent transport checks:

```sh
python3 apps/display/receive.py --sink headless --port 5004 \
  --seconds 20 --require-frames 100
```

Send the Mac test stream to that same port. `--require-frames` fails the check
if too few frames decode. Exit JSON contains decoded frames, sink render/drop
counts, and stream-gap transitions. Periodic logs include jitter-buffer packet
loss/late counts. Headless render counters mean buffers consumed, not optical
display. `--windowed` is available for local desktop diagnostics.

## Verified on October 3, 2026

- Raspberry Pi 5, Debian 13.7 arm64, GStreamer 1.26.2.
- Mac 1280x720/30 HEVC -> Pi hardware decoder -> Wayland, with observed sink
  output around 30 fps in the first bounded test.
- Later hotspot playback had frequent frame gaps. Waiting for a keyframe and
  retaining the previous image keeps the HUD visible between updates.
- The persistent receiver was inspected with a Wayland screenshot: HUD filled
  the 1920x1080 display with no desktop visible. The service remained on the
  same PID with zero restarts during the observation period.

The first attempt to join the running stream without keyframe recovery caused
a decoder error and SIGSEGV; the current settings recovered a stable process.
This does not establish sustained loss resilience, optical correctness in the
glasses, or motion-to-photon latency. See the [bench record](../../hardware/pi-bench-2026-10-03.md).


### XREAL audio

Install `config/pi/helmetd-audio.service` into `~/.config/systemd/user/`, then run `systemctl --user daemon-reload` and `systemctl --user enable --now helmetd-audio`. It receives mono RTP/L16, 48 kHz, payload 98 on UDP 5010, buffers 100 ms, and plays stereo directly through the Pi 5 HDMI-0 ALSA device at 40% gain. The hardware device is explicit so an unavailable PipeWire profile cannot redirect speech to Dummy Output. Adjust `plughw:CARD=vc4hdmi0,DEV=0` if using HDMI-1. Requires the GStreamer ALSA plugin.

`tools/helmet.sh --pi <address>` stores the destination in the ignored `.local/pi-audio.json`. The console forwards ElevenLabs WebRTC 48 kHz PCM through the guarded local API, silences local conversation playback, and uses local Mac speech synthesis for navigation cues sent to the same receiver. Refresh an existing console after updating. Native voice sessions also use this destination; `--macbook` explicitly retains Mac playback. The microphone remains on the Mac: this HDMI connection provides no microphone return path.

The service and HDMI stream can be verified with `systemctl --user status helmetd-audio`, `wpctl status` and `/proc/asound/card0/pcm0p/sub0/status`. Successful UDP sends do not prove audible playback; verify with the wearer. The link uses the same trusted local network as the video stream.
