"""Exercise the real HEVC encoder, RTP sender, and hardware decoder on macOS."""

import argparse
import selectors
import socket
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sender", required=True)
    parser.add_argument("--gst-launch", required=True)
    args = parser.parse_args()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]

    receiver_command = [
        args.gst_launch, "-e", "udpsrc", "address=127.0.0.1", f"port={port}",
        "caps=application/x-rtp,media=video,encoding-name=H265,payload=96,clock-rate=90000",
        "!", "rtpjitterbuffer", "latency=20", "drop-on-latency=true",
        "!", "rtph265depay", "!", "video/x-h265,stream-format=byte-stream,alignment=au",
        "!", "h265parse", "!", "vtdec_hw",
        # Avoid negotiating GLMemory in a headless test without a Cocoa loop.
        "!", "video/x-raw,format=NV12",
        "!", "fakesink", "sync=false", "num-buffers=30",
    ]
    receiver = subprocess.Popen(
        receiver_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    log = bytearray()
    try:
        # Wait for the receiver's live pipeline clock instead of racing startup.
        deadline = time.monotonic() + 15
        with selectors.DefaultSelector() as selector:
            selector.register(receiver.stdout, selectors.EVENT_READ)
            while b"New clock:" not in log:
                if time.monotonic() > deadline:
                    raise RuntimeError("Receiver did not become ready")
                for key, _ in selector.select(timeout=0.1):
                    chunk = key.fileobj.read1(4096)
                    log.extend(chunk)
                    if not chunk:
                        raise RuntimeError("Receiver exited before starting")

        sender = subprocess.run(
            [args.sender, "--host", "127.0.0.1", "--port", str(port),
             "--width", "640", "--height", "360", "--frames", "90"],
            capture_output=True, text=True, timeout=20,
        )
        print(sender.stdout, end="")
        if sender.returncode:
            raise RuntimeError(sender.stderr)
        remaining, _ = receiver.communicate(timeout=10)
        log.extend(remaining)
        if receiver.returncode != 0 or b"Got EOS" not in log:
            raise RuntimeError("Receiver failed to decode 30 frames")
        print("PASS: received and hardware-decoded 30 HEVC frames over loopback RTP/UDP.")
    except Exception:
        print(log.decode(errors="replace"))
        raise
    finally:
        if receiver.poll() is None:
            receiver.terminate()
            try:
                receiver.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                receiver.kill()
                receiver.communicate()


if __name__ == "__main__":
    main()
