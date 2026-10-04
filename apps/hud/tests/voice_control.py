"""Real Unix-socket controls against the native Metal renderer; no cloud calls."""

import argparse
import json
import socket
import subprocess
import tempfile
import time
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hud", required=True, type=Path)
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="hctrl-", dir="/tmp") as temporary:
        directory = Path(temporary)
        outputs = args.directory or directory
        outputs.mkdir(parents=True, exist_ok=True)
        server = directory / "hud.sock"
        snapshot = outputs / "copilot.png"
        assert not snapshot.exists(), "Choose a new output directory"
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.bind(str(directory / "client.sock"))
            client.settimeout(1)
            process = subprocess.Popen(
                [
                    str(args.hud.resolve()),
                    "--headless",
                    "--camera",
                    "test",
                    "--control-socket",
                    str(server),
                    "--frames",
                    "150",
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
            try:
                deadline = time.monotonic() + 5
                while not server.exists():
                    assert process.poll() is None and time.monotonic() < deadline
                    time.sleep(0.05)

                def command(text):
                    nonce = uuid.uuid4().hex
                    client.sendto(f"{nonce} {text}".encode(), str(server))
                    result = json.loads(client.recv(8192))
                    assert result["request_id"] == nonce
                    return result

                assert command("mode focus")["panels"] == 4
                assert command("panel camera on")["panels"] == 5
                assert command("panel camera on")["panels"] == 5
                assert command("panel nav off")["panels"] == 5
                assert command("diagnostics on")["diagnostics"]
                assert not command("diagnostics off")["diagnostics"]
                assert command("mode clear")["panels"] == 0
                assert command("mode unsupported")["status"] == "error"
                assert command("status")["panels"] == 0
                assert command("mode full")["panels"] == 7
                assert command("status")["detections"] == []
                # The heartbeat renders a bounded indicator; no microphone is used.
                while process.poll() is None:
                    try:
                        assert command("phase speaking")["status"] == "ok"
                    except (FileNotFoundError, ConnectionRefusedError, TimeoutError):
                        break
                    time.sleep(0.25)
                log, _ = process.communicate(timeout=10)
                assert process.returncode == 0, log
                assert snapshot.is_file() and not server.exists()
                if args.directory:
                    (outputs / "hud.log").write_text(log)
                print(
                    "PASS: HUD modes, idempotent panels, diagnostics, replies and voice indicator"
                )
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.communicate(timeout=10)


if __name__ == "__main__":
    main()
