#!/usr/bin/env python3
"""Download the exact OpenCV Zoo YOLOX-S model used by helmetd (Apache-2.0)."""

import hashlib
import tempfile
import urllib.request
from pathlib import Path

NAME = "object_detection_yolox_2022nov.onnx"
SHA256 = "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063"
URL = f"https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/object_detection_yolox/{NAME}"
DESTINATION = Path(__file__).resolve().parents[1] / ".local" / "models" / NAME


def main():
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    if DESTINATION.exists():
        if hashlib.sha256(DESTINATION.read_bytes()).hexdigest() != SHA256:
            raise SystemExit(f"Existing model has an unexpected hash: {DESTINATION}")
        print(f"Model verified: {DESTINATION}")
        return
    temporary = None
    try:
        print("Downloading YOLOX-S (35.9 MB)…", flush=True)
        with tempfile.NamedTemporaryFile(dir=DESTINATION.parent, delete=False) as output:
            temporary = Path(output.name)
            with urllib.request.urlopen(URL, timeout=30) as source:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != SHA256:
            raise RuntimeError("Model checksum mismatch; download was not installed")
        temporary.replace(DESTINATION)
        print(f"Model verified: {DESTINATION}")
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
