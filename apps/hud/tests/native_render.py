"""Render real Metal frames, encode/decode HEVC, and inspect the resulting pixels."""

import argparse
import os
import socket
import time
import subprocess
import tempfile
from pathlib import Path


def run(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def pixels_in(frame, x, y, width, height):
    for row in range(y, y + height):
        for col in range(x, x + width):
            offset = (row * 640 + col) * 3
            yield tuple(frame[offset : offset + 3])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hud", required=True)
    parser.add_argument("--gst-launch", required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="helmetd-metal-") as directory:
        root = Path(directory)
        recording, snapshot, decoded = [
            root / name for name in ("hud.mp4", "hud.png", "decoded.rgb")
        ]
        print(
            run(
                [
                    args.hud,
                    "--headless",
                    "--warning",
                    "--demo",
                    "--width",
                    "640",
                    "--height",
                    "360",
                    "--frames",
                    "45",
                    "--output",
                    str(recording),
                    "--snapshot",
                    str(snapshot),
                ]
            )
        )
        assert snapshot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "No rendered snapshot"
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
        assert len(video) % frame_size == 0 and len(video) >= 30 * frame_size, (
            "Too few complete decoded frames"
        )
        frame = video[-frame_size:]
        # Check semantics and orientation after the full render/codec path.
        warning = list(pixels_in(frame, 470, 195, 140, 36))
        assert sum(r > 150 and 65 < g < 220 and b < 110 for r, g, b in warning) > 100, (
            "Amber warning missing/misplaced"
        )
        speed = list(pixels_in(frame, 262, 300, 42, 35))
        assert sum(min(rgb) > 170 for rgb in speed) > 150, "Speed text missing/misplaced"
        center = list(pixels_in(frame, 190, 100, 260, 140))
        assert sum(max(rgb) < 12 for rgb in center) > len(center) * 0.99, (
            "Center of view should stay black"
        )
        camera = list(pixels_in(frame, 34, 218, 140, 77))
        assert all(max(rgb) < 12 for rgb in camera), "Auto ride view must hide camera video"
        # Guard against overwriting a prior recording/snapshot.
        before = recording.read_bytes()
        retry = subprocess.run(
            [args.hud, "--headless", "--frames", "1", "--output", str(recording)],
            capture_output=True,
            timeout=5,
        )
        assert retry.returncode != 0 and recording.read_bytes() == before, (
            "Existing capture overwritten"
        )
        # Exercise independent composition, including a genuinely empty frame.
        regions = {"camera": (24, 190, 170, 145), "nav": (24, 200, 170, 135),
                   "telemetry": (260, 298, 145, 45)}
        for panel in ("none", *regions):
            png, raw = root / f"{panel}.png", root / f"{panel}.rgb"
            run([args.hud, "--headless", "--camera", "none",
                 "--panels", panel, "--width", "640", "--height", "360",
                 "--frames", "1", "--snapshot", str(png)])
            run([args.gst_launch, "-q", "filesrc", f"location={png}", "!", "pngdec",
                 "!", "videoconvert", "!", "video/x-raw,format=RGB", "!", "filesink",
                 f"location={raw}"])
            image = raw.read_bytes()
            assert len(image) == frame_size, "Incomplete panel snapshot"
            if panel == "none":
                assert not any(image), "Hidden panels left nonblack pixels"
                continue
            assert all(max(pixel) < 12 for pixel in pixels_in(image, 220, 90, 200, 130)), (
                "Reference layout must keep the center clear"
            )
        # Exercise the real local frame bridge, stale timeout and camera arbitration.
        for mode in ("minimal", "fresh", "stale", "camera", "warning"):
            bridge = root / "hud-map.bgra"
            bridge.write_bytes(bytes([20, 80, 220, 255]) * (640 * 360))
            if mode == "stale":
                os.utime(bridge, (time.time()-10, time.time()-10))
            server, local = root / "map.sock", root / "client.sock"
            png, raw = root / f"map-{mode}.png", root / f"map-{mode}.rgb"
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
                client.bind(str(local)); client.settimeout(2)
                process = subprocess.Popen([args.hud, "--headless", "--camera", "none",
                    "--panels", "camera,nav", "--width", "640", "--height", "360",
                    "--frames", "30", "--control-socket", str(server), "--snapshot", str(png)] + (["--warning"] if mode == "warning" else []) + ([] if mode == "minimal" else ["--diagnostics"]),
                    stdout=subprocess.DEVNULL)
                try:
                    deadline=time.monotonic()+5
                    while not server.exists() and time.monotonic()<deadline: time.sleep(.01)
                    client.sendto(b"map nav_map active 500 500 2 0 0 1000 1000",str(server));client.recv(8192)
                    if mode == "camera":
                        client.sendto(b"camera camera front",str(server));client.recv(8192)
                    process.wait(timeout=5)
                    assert process.returncode == 0
                finally:
                    if process.poll() is None: process.kill();process.wait()
                    local.unlink(missing_ok=True)
            run([args.gst_launch,"-q","filesrc",f"location={png}","!","pngdec","!",
                "videoconvert","!","video/x-raw,format=RGB","!","filesink",f"location={raw}"])
            colors=list(pixels_in(raw.read_bytes(),36,220,140,80))
            matches=sum(r>200 and 60<g<100 and b<35 for r,g,b in colors)
            assert (matches>10000) if mode in ("minimal", "fresh", "warning") else (matches==0), (mode,matches)
        print("PASS: Metal/HEVC preserves content; panels hide independently on pure black.")


if __name__ == "__main__":
    main()
