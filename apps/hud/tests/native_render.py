"""Render real Metal frames, encode/decode HEVC, and inspect the resulting pixels."""

import argparse
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
        warning = list(pixels_in(frame, 210, 72, 220, 45))
        assert sum(r > 150 and 65 < g < 220 and b < 110 for r, g, b in warning) > 200, (
            "Amber warning missing/misplaced"
        )
        speed = list(pixels_in(frame, 262, 262, 60, 55))
        assert sum(min(rgb) > 170 for rgb in speed) > 150, "Speed text missing/misplaced"
        center = list(pixels_in(frame, 170, 140, 245, 100))
        assert sum(max(rgb) < 12 for rgb in center) > len(center) * 0.99, (
            "Center of view should stay black"
        )
        camera = list(pixels_in(frame, 444, 210, 168, 90))
        assert sum(min(rgb) > 180 for rgb in camera) > 20, "Camera texture missing"
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
        print("PASS: Metal/HEVC preserves the warning, text, camera, and clear center.")


if __name__ == "__main__":
    main()
