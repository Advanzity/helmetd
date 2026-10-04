"""Exercise the H.264 camera uplink concurrently with HEVC HUD output, then stall it."""

import argparse
import selectors
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from native_render import pixels_in, run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hud", required=True)
    parser.add_argument("--gst-launch", required=True)
    parser.add_argument("--reject-profile", action="store_true")
    args = parser.parse_args()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="helmetd-camera-") as directory:
        root = Path(directory)
        recording, decoded = root / "hud.mp4", root / "hud.rgb"
        hud = subprocess.Popen(
            [
                args.hud,
                "--headless",
                "--camera",
                "udp",
                "--control-socket", str(root / "hud.sock"),
                "--camera-label", "FRONT",
                "--camera-port",
                str(port),
                "--width",
                "640",
                "--height",
                "360",
                "--frames",
                "180",
                "--output",
                str(recording),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        log = bytearray()
        try:
            deadline = time.monotonic() + 10
            with selectors.DefaultSelector() as selector:
                selector.register(hud.stdout, selectors.EVENT_READ)
                while b"HEVC recording ->" not in log:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("HUD did not become ready")
                    for key, _ in selector.select(timeout=0.1):
                        chunk = key.fileobj.read1(4096)
                        if not chunk:
                            raise RuntimeError(log.decode(errors="replace"))
                        log.extend(chunk)
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as control:
                control.bind(str(root / "client.sock"))
                control.settimeout(2)
                control.sendto(b"test camera front", str(root / "hud.sock"))
                assert b'"status":"ok"' in control.recv(8192)
            run(
                [
                    args.gst_launch,
                    "-q",
                    "videotestsrc",
                    "is-live=true",
                    "pattern=ball",
                    "num-buffers=75",
                    "!",
                    "video/x-raw,width=640,height=360,framerate=30/1",
                    "!",
                    "videoconvert",
                    "!",
                    "video/x-raw,format=NV12",
                    "!",
                    "vtenc_h264_hw",
                    "realtime=true",
                    "allow-frame-reordering=false",
                    "max-keyframe-interval=30",
                    "!",
                    f"video/x-h264,profile={'main' if args.reject_profile else 'baseline'}",
                    "!",
                    "h264parse",
                    "!",
                    "rtph264pay",
                    "pt=97",
                    "config-interval=-1",
                    "!",
                    "udpsink",
                    "host=127.0.0.1",
                    f"port={port}",
                    "sync=false",
                ]
            )
            remaining, _ = hud.communicate(timeout=15)
            log.extend(remaining)
            assert hud.returncode == 0, log.decode(errors="replace")
            print(log.decode(errors="replace"))
        finally:
            if hud.poll() is None:
                hud.terminate()
                try:
                    hud.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    hud.kill()
                    hud.communicate()
        run(
            [
                args.gst_launch,
                "-q",
                "filesrc",
                f"location={recording}",
                "!",
                "qtdemux",
                "!",
                "h265parse",
                "!",
                "vtdec_hw",
                "!",
                "video/x-raw,format=NV12",
                "!",
                "videoconvert",
                "!",
                "video/x-raw,format=RGB",
                "!",
                "filesink",
                f"location={decoded}",
            ]
        )
        video = decoded.read_bytes()
        frame_size = 640 * 360 * 3
        frames = [video[i : i + frame_size] for i in range(0, len(video), frame_size)]
        assert len(frames) >= 120, "Incomplete HUD recording"

        def bright_camera_pixels(frame):
            # Identify the white test ball, not the brighter gray unavailable
            # labels (including codec ringing at their edges).
            return sum(min(rgb) > 230 for rgb in pixels_in(frame, 34, 218, 140, 77))

        if args.reject_profile:
            assert b"Camera unavailable:" in log, "Unsupported profile did not report failure"
            assert all(bright_camera_pixels(frame) == 0 for frame in frames), (
                "Unsupported camera image was shown"
            )
            print("PASS: camera profile rejected; HUD rendering/encoding continues.")
            return
        assert any(bright_camera_pixels(frame) > 20 for frame in frames[:100]), (
            "H.264 uplink never reached the camera texture"
        )
        assert all(bright_camera_pixels(frame) == 0 for frame in frames[-15:]), (
            "Stalled camera image was left visible"
        )
        print(
            "PASS: simultaneous H.264 input / Metal HUD / HEVC output, then stale camera removal."
        )


if __name__ == "__main__":
    main()
