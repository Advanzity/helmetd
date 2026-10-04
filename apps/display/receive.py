#!/usr/bin/env python3
"""Persistent Pi HEVC hardware HUD receiver; hold last frame during demo pauses."""

import argparse
import json
import os
import signal
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--sink", choices=("wayland", "headless"), default="wayland")
    parser.add_argument("--windowed", action="store_true")
    parser.add_argument("--jitter-ms", type=int, default=120)
    parser.add_argument("--stale-ms", type=int, default=500)
    parser.add_argument("--seconds", type=int, default=0, help="0 runs until Ctrl-C")
    parser.add_argument("--require-frames", type=int, default=0, help="Fail if fewer network frames decode")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not 0 <= args.jitter_ms <= 1000:
        parser.error("invalid port or jitter budget")
    if not 100 <= args.stale_ms <= 10000 or args.seconds < 0 or args.require_frames < 0:
        parser.error("stale-ms must be 100–10000; seconds/require-frames must be nonnegative")
    if args.sink == "wayland":
        os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        os.environ.setdefault("WAYLAND_DISPLAY", "wayland-0")

    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import GLib, Gst
    Gst.init(None)
    if not Gst.ElementFactory.find("v4l2slh265dec"):
        parser.error("v4l2slh265dec hardware decoder is unavailable; no software fallback")
    sink = "waylandsink" if args.sink == "wayland" else "fakesink"
    description = (
        f'udpsrc port={args.port} caps="application/x-rtp,media=video,encoding-name=H265,payload=96,clock-rate=90000"'
        f" ! rtpjitterbuffer name=jitter latency={args.jitter_ms} drop-on-latency=true"
        " ! rtph265depay wait-for-keyframe=true ! video/x-h265,stream-format=byte-stream,alignment=au"
        " ! h265parse ! v4l2slh265dec name=decoder"
        " ! queue max-size-buffers=2 max-size-bytes=0 max-size-time=0 leaky=downstream"
        # labwc's direct NV12 scanout used full-range BT.601 for our limited
        # BT.709 stream. Convert using decoded colorimetry before presentation,
        # so black is RGB zero even when the compositor bypasses its shaders.
        " ! videoconvert ! video/x-raw,format=BGRx,colorimetry=sRGB"
        f" ! {sink} name=display sync=false enable-last-sample=false"
    )
    pipeline = Gst.parse_launch(description)
    video = pipeline.get_by_name("decoder").get_static_pad("src")
    display = pipeline.get_by_name("display")
    loop = GLib.MainLoop()
    state = {"decoded": 0, "stale_transitions": 0, "recoveries": 0, "failed": False}
    last_frame = None
    live = False

    def decoded(_pad, _info):
        nonlocal last_frame
        state["decoded"] += 1
        last_frame = time.monotonic()
        return Gst.PadProbeReturn.OK

    def watchdog():
        nonlocal live
        fresh = last_frame is not None and (time.monotonic() - last_frame) * 1000 < args.stale_ms
        if fresh != live:
            live = fresh
            state["recoveries" if live else "stale_transitions"] += 1
            print("HUD live" if live else "HUD stale: retaining last frame", flush=True)
        return True

    def message(_bus, msg):
        if msg.type == Gst.MessageType.ERROR:
            error, detail = msg.parse_error()
            print(f"Display error: {error}; {detail}", file=sys.stderr, flush=True)
            state["failed"] = True
            loop.quit()
        elif msg.type == Gst.MessageType.EOS:
            loop.quit()

    def stop(*_):
        loop.quit()
        return False

    def fullscreen():
        if not display.get_property("stats").get_value("rendered"):
            return True
        if not args.windowed:
            display.set_property("fullscreen", True)
            print("Fullscreen requested after first rendered frame", flush=True)
        return False

    def report():
        stats = display.get_property("stats")
        rtp = pipeline.get_by_name("jitter").get_property("stats")
        print(f"Display stats: decoded={state['decoded']} rendered={stats.get_value('rendered')} dropped={stats.get_value('dropped')} live={live}; RTP lost={rtp.get_value('num-lost')} late={rtp.get_value('num-late')}", flush=True)
        return True

    video.add_probe(Gst.PadProbeType.BUFFER, decoded)
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", message)
    for sig in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, stop)
    GLib.timeout_add(50, watchdog)
    GLib.timeout_add_seconds(10, report)
    if args.seconds:
        GLib.timeout_add_seconds(args.seconds, stop)
    if args.sink == "wayland":
        GLib.timeout_add(250, fullscreen)
    print(f"Listening UDP {args.port}; HEVC PT96 hardware v4l2slh265dec; RGB presentation; sink={args.sink}; stale={args.stale_ms}ms", flush=True)
    try:
        if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Cannot start display pipeline")
        loop.run()
    finally:
        stats = display.get_property("stats")
        state["sink_rendered"] = stats.get_value("rendered") if stats else 0
        state["sink_dropped"] = stats.get_value("dropped") if stats else 0
        pipeline.set_state(Gst.State.NULL)
        print(json.dumps(state, sort_keys=True), flush=True)
    return 1 if state["failed"] or state["decoded"] < args.require_frames else 0


if __name__ == "__main__":
    sys.exit(main())
