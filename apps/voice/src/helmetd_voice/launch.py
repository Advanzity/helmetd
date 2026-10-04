"""Start the HUD and copilot together; only shut down processes we created."""

import socket
import subprocess
import time
from pathlib import Path

from .agent import configure_agent
from .copilot import HudClient
from .voice import talk


def launch(camera="udp", host="172.20.10.5", preview=False, hud_only=False):
    binary = Path("build/mac-debug/bin/helmetd-hud")
    model = Path(".local/models/object_detection_yolox_2022nov.onnx")
    if not binary.is_file():
        raise ValueError("Build the HUD first: cmake --build --preset mac-debug")
    if camera != "none" and not model.is_file():
        raise ValueError("Download the detector first: python3 tools/download_detector.py")
    directory = Path(".local/copilot")
    directory.mkdir(parents=True, exist_ok=True)
    client = HudClient()
    process = log = None
    try:
        if client.request("status")["status"] != "ok":
            if camera == "udp":
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                    try:
                        probe.bind(("0.0.0.0", 5002))
                    except OSError:
                        raise ValueError(
                            "Camera port 5002 is in use. Quit the older HUD first, "
                            "or use --camera test --preview for a local demo."
                        ) from None
            command = [str(binary), "--camera", camera, "--control-socket", str(client.path)]
            if camera != "none":
                command += ["--detect-model", str(model), "--voice-port", "8014"]
            if not preview:
                command += ["--host", host]
            log = (directory / "hud.log").open("a")
            process = subprocess.Popen(command, stdout=log, stderr=log)
            deadline = time.monotonic() + 10
            while client.request("status")["status"] != "ok":
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise ValueError("HUD did not start. See .local/copilot/hud.log")
                time.sleep(0.1)
        print(
            "HUD control connected. Ctrl-C stops this launcher and any HUD it started.", flush=True
        )
        if hud_only:
            if process:
                process.wait()
            return
        configure_agent()
        talk(with_alerts=True)
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if log:
            log.close()
