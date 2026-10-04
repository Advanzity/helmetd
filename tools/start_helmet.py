"""Start the local helmet MVP without tying its lifetime to a terminal."""
import argparse
import fcntl
import json
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

from helmetd_voice.copilot import HudClient

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pi', default='BigDaddyD.local', help='Verified Pi hostname or IP')
    args = parser.parse_args()
    directory = ROOT / '.local/pi-runtime'
    directory.mkdir(parents=True, exist_ok=True)
    host = socket.gethostbyname(args.pi)
    (ROOT/'.local/pi-audio.json').write_text(json.dumps({'host': host, 'port': 5010}))
    with (directory / 'start.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        hud = HudClient(ROOT / '.local/hud-control.sock')
        if hud.request('status')['status'] != 'ok':
            host = socket.gethostbyname(args.pi)
            binary = ROOT / 'build/mac-debug/bin/Helmetd.app'
            model = ROOT / '.local/models/object_detection_yolox_2022nov.onnx'
            if not binary.is_dir() or not model.is_file():
                raise SystemExit('Build the HUD and run tools/download_detector.py first.')
            # Refuse a duplicate unmanaged UDP consumer.
            for port in (5002, 5004, 5006, 5008):
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                    try:
                        probe.bind(('0.0.0.0', port))
                    except OSError:
                        raise SystemExit(f'Camera port {port} is occupied; close the old HUD first.') from None
            subprocess.run(['open', '-n', '-g', '--stdout', str(directory/'hud.log'),
                '--stderr', str(directory/'hud-errors.log'), str(binary), '--args',
                '--camera', 'udp', '--camera-label', 'FRONT', '--camera-port', '5002',
                '--extra-camera', 'LEFT:5004', '--extra-camera', 'RIGHT:5006',
                '--extra-camera', 'REAR:5008', '--detect-model', str(model),
                '--host', host, '--bitrate', '2500', '--control-socket', str(hud.path),
                '--voice-port', '8014', '--record-dir', str(ROOT/'.local/recordings/rolling'), '--frames', '0'], check=True)
            deadline = time.monotonic() + 45
            while hud.request('status')['status'] != 'ok':
                if time.monotonic() > deadline:
                    raise SystemExit('HUD startup timed out. See .local/pi-runtime/hud-errors.log.')
                time.sleep(.2)
            try:
                layout = json.loads((ROOT/'.local/hud-layout.json').read_text())
                if layout.get('camera_view') in ('auto', 'front', 'left', 'right', 'rear') and type(layout.get('panels')) is int and 0 <= layout['panels'] <= 7:
                    hud.request('mode quiet' if layout.get('quiet') else 'mode full')
                    hud.request('camera '+layout['camera_view'])
                    for name, bit in (('camera', 1), ('nav', 2), ('telemetry', 4)):
                        hud.request(f"panel {name} {'on' if layout['panels'] & bit else 'off'}")
            except (OSError, ValueError):
                pass
        with socket.socket() as probe:
            console_running = probe.connect_ex(('127.0.0.1', 8016)) == 0
        if not console_running:
            with (directory/'console.log').open('a') as log:
                process = subprocess.Popen(['sh', str(ROOT/'tools/voice.sh'), 'web-test'],
                    cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                    start_new_session=True)
            deadline = time.monotonic() + 20
            while True:
                try:
                    with urllib.request.urlopen('http://127.0.0.1:8016/', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                if process.poll() is not None or time.monotonic() > deadline:
                    raise SystemExit('Console startup failed. See .local/pi-runtime/console.log.')
                time.sleep(.2)
        renderer = ROOT / 'build/mac-debug/bin/helmetd-map-renderer'
        if renderer.is_file():
            with (directory/'map-renderer.log').open('a') as log:
                subprocess.Popen([str(renderer), str(directory/'map-renderer.lock')],
                    cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                    start_new_session=True)
        print('HUD ready. Open http://127.0.0.1:8016 in Zen or Chrome for navigation and audio.')
        print('Processes continue after this command exits. Re-running reuses the running services.')


if __name__ == '__main__':
    main()
