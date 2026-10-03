#!/usr/bin/env python3
"""Pi camera/test source -> baseline H.264 RTP for the native Mac HUD."""

import argparse
import signal
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Mac LAN address")
    parser.add_argument("--port", type=int, default=5002)
    parser.add_argument("--source", choices=("test", "usb", "csi"), required=True)
    parser.add_argument("--device", default="/dev/video0", help="USB V4L2 device")
    parser.add_argument("--usb-format", choices=("raw", "mjpeg"), default="raw")
    parser.add_argument("--camera-name", help="libcamera camera name from gst-device-monitor")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--bitrate", type=int, default=1500, help="H.264 kbps")
    parser.add_argument("--seconds", type=int, default=0, help="0 runs until Ctrl-C")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not 1 <= args.fps <= 60:
        parser.error("port must be 1–65535 and fps must be 1–60")
    if any(n < 2 or n > 1920 or n % 2 for n in (args.width, args.height)):
        parser.error("dimensions must be even and between 2 and 1920")
    if args.bitrate <= 0 or args.seconds < 0:
        parser.error("bitrate must be positive and seconds nonnegative")

    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import GLib, Gst
    Gst.init(None)
    size = f"width={args.width},height={args.height},framerate={args.fps}/1"
    if args.source == "test":
        source = f'videotestsrc name=camera is-live=true pattern=ball ! video/x-raw,{size} ! textoverlay text="PI TEST SOURCE" valignment=top'
    elif args.source == "usb":
        source = "v4l2src name=camera do-timestamp=true ! "
        source += f"image/jpeg,{size} ! jpegdec" if args.usb_format == "mjpeg" else f"video/x-raw,{size}"
    else:
        source = f"libcamerasrc name=camera ! video/x-raw,{size}"
    description = (
        source
        + " ! queue max-size-buffers=2 max-size-bytes=0 max-size-time=0 leaky=downstream"
        + " ! videoconvert ! video/x-raw,format=I420"
        + f" ! x264enc name=encoder tune=zerolatency speed-preset=ultrafast bitrate={args.bitrate} key-int-max={args.fps} bframes=0 byte-stream=true"
        + " ! video/x-h264,profile=constrained-baseline ! h264parse"
        + " ! rtph264pay pt=97 mtu=1200 config-interval=-1 aggregate-mode=none"
        + " ! udpsink name=network sync=false async=false"
    )
    pipeline = Gst.parse_launch(description)
    camera = pipeline.get_by_name("camera")
    if args.source == "usb":
        camera.set_property("device", args.device)
    if args.source == "csi" and args.camera_name:
        camera.set_property("camera-name", args.camera_name)
    network = pipeline.get_by_name("network")
    network.set_property("host", args.host)
    network.set_property("port", args.port)
    loop = GLib.MainLoop()
    frames = 0
    failed = False

    def encoded(_pad, _info):
        nonlocal frames
        frames += 1
        return Gst.PadProbeReturn.OK

    def message(_bus, msg):
        nonlocal failed
        if msg.type == Gst.MessageType.ERROR:
            error, detail = msg.parse_error()
            print(f"Capture error: {error}; {detail}", file=sys.stderr, flush=True)
            failed = True
            loop.quit()
        elif msg.type == Gst.MessageType.EOS:
            loop.quit()

    def stop(*_):
        loop.quit()
        return False

    pipeline.get_by_name("encoder").get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, encoded)
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", message)
    for sig in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, stop)
    if args.seconds:
        GLib.timeout_add_seconds(args.seconds, stop)
    print(f"Source={args.source}; software x264 constrained-baseline {args.width}x{args.height}@{args.fps}; RTP PT97 -> {args.host}:{args.port}", flush=True)
    try:
        if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Cannot start capture pipeline")
        loop.run()
    finally:
        pipeline.set_state(Gst.State.NULL)
        print(f"Capture stopped: source={args.source} encoded_frames={frames}", flush=True)
    return 1 if failed or frames == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
