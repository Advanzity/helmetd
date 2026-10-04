"""Opt-in real YOLOX/RTP/Metal check, using a local photo with a central person.

Run with --hud, --model, --image and --directory. Requires GStreamer and the
downloaded model; does not download images or weights during the test.
"""

import argparse
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path


def stop(process):
    if process.poll() is None:
        process.terminate()
    try:
        process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("hud", "model", "image", "directory"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    gst = shutil.which("gst-launch-1.0")
    assert gst, "GStreamer required"
    args.directory.mkdir(parents=True, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    for stale in (False, True):
        stem = "stale" if stale else "active"
        snapshot = args.directory / f"{stem}.png"
        raw = args.directory / f"{stem}.rgb"
        assert not snapshot.exists() and not raw.exists(), "Choose a new result directory"
        sender = subprocess.Popen(
            [
                gst,
                "-q",
                "filesrc",
                f"location={args.image.resolve()}",
                "!",
                "jpegdec",
                "!",
                "imagefreeze",
                "is-live=true",
                "!",
                "video/x-raw,framerate=15/1",
                "!",
                "videoscale",
                "!",
                "videoconvert",
                "!",
                "video/x-raw,format=NV12,width=640,height=360,pixel-aspect-ratio=1/1",
                "!",
                "vtenc_h264_hw",
                "realtime=true",
                "allow-frame-reordering=false",
                "bitrate=1500",
                "max-keyframe-interval=15",
                "!",
                "video/x-h264,profile=baseline",
                "!",
                "rtph264pay",
                "pt=97",
                "config-interval=-1",
                "mtu=1200",
                "!",
                "udpsink",
                "host=127.0.0.1",
                f"port={port}",
                "sync=false",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        hud = None
        try:
            hud = subprocess.Popen(
                [
                    str(args.hud.resolve()),
                    "--headless",
                    "--camera",
                    "udp",
                    "--camera-port",
                    str(port),
                    "--detect-model",
                    str(args.model.resolve()),
                    "--frames",
                    "240",
                    "--width",
                    "640",
                    "--height",
                    "360",
                    "--snapshot",
                    str(snapshot),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if stale:
                time.sleep(4)
                assert sender.poll() is None, "Sender exited before the simulated dropout"
                stop(sender)
            log, _ = hud.communicate(timeout=35)
            (args.directory / f"{stem}.log").write_text(log)
            assert hud.returncode == 0, log
            match = re.search(r"Detection results (\d+); caution results (\d+)", log)
            assert match and int(match[1]) >= 3 and int(match[2]) > 0, log
            subprocess.run(
                [
                    gst,
                    "-q",
                    "filesrc",
                    f"location={snapshot}",
                    "!",
                    "pngdec",
                    "!",
                    "videoconvert",
                    "!",
                    "video/x-raw,format=RGB",
                    "!",
                    "filesink",
                    f"location={raw}",
                ],
                check=True,
                timeout=10,
                capture_output=True,
            )
            pixels = raw.read_bytes()
            assert len(pixels) == 640 * 360 * 3, "Unexpected snapshot dimensions"

            def area(x, y, width, height):
                for row in range(y, y + height):
                    for col in range(x, x + width):
                        offset = (row * 640 + col) * 3
                        yield tuple(pixels[offset : offset + 3])

            amber = sum(r > 150 and 65 < g < 230 and b < 110 for r, g, b in area(470, 195, 140, 36))
            assert amber == 0 if stale else amber > 100, (
                f"{stem}: unexpected caution pixels {amber}"
            )
            if stale:
                inset = list(area(34, 218, 140, 77))
                assert sum(max(p) - min(p) > 60 for p in inset) < 20, (
                    "Old camera image remained visible"
                )
            print(
                f"PASS {stem}: detections={match[1]}, caution updates={match[2]}, "
                f"snapshot={snapshot}"
            )
        finally:
            if hud:
                stop(hud)
            stop(sender)


if __name__ == "__main__":
    main()
