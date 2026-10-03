# Pi HUD display

`receive.py` receives the Mac's HEVC RTP/UDP stream, hardware-decodes it with
`v4l2slh265dec`, and displays it through `waylandsink`. On the tested Pi this
negotiates DMA-BUF NV12 directly from `/dev/video19` to the existing Wayland
desktop. It does not stop the compositor or claim DRM ownership. Python drives
the GStreamer lifecycle; pixels stay in the native media pipeline.

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
