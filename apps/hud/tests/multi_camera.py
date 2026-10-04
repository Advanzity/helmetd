"""Real three-stream decoding, independent expiry, and signal camera routing."""
import argparse
import json
import socket
import subprocess
import tempfile
import time
from pathlib import Path


def stop(process):
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hud', required=True)
    parser.add_argument('--gst-launch', required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='hudmulti-', dir='/tmp') as directory:
        root = Path(directory)
        reservations = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in range(3)]
        for reservation in reservations:
            reservation.bind(('127.0.0.1', 0))
        ports = [reservation.getsockname()[1] for reservation in reservations]
        for reservation in reservations:
            reservation.close()
        processes = []
        with (root/'hud.log').open('w+') as log, socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.bind(str(root/'client.sock'))
            client.settimeout(1)
            command = [args.hud, '--headless', '--camera', 'none', '--camera-label', 'FRONT',
                       '--frames', '900', '--panels', 'camera', '--width', '640', '--height', '360',
                       '--record-dir', str(root/'rolling'), '--control-socket', str(root/'hud.sock'), '--snapshot', str(root/'hud.png')]
            for label, port in zip(('LEFT', 'RIGHT', 'REAR'), ports):
                command += ['--extra-camera', f'{label}:{port}']
            hud = subprocess.Popen(command, stdout=log, stderr=log)
            processes.append(hud)

            def request(command='status'):
                client.sendto(('test '+command).encode(), str(root/'hud.sock'))
                return json.loads(client.recv(8192))

            def until(predicate, seconds=12):
                deadline = time.monotonic()+seconds
                while time.monotonic()<deadline:
                    if hud.poll() is not None:
                        raise AssertionError((root/'hud.log').read_text())
                    try:
                        state = request()
                        if predicate(state):
                            return state
                    except (OSError, ValueError):
                        pass
                    time.sleep(.1)
                raise AssertionError('Expected camera state did not arrive: '+(root/'hud.log').read_text())

            try:
                until(lambda state: state['status']=='ok')
                senders = []
                for pattern, port in zip(('red', 'green', 'blue'), ports):
                    sender = subprocess.Popen([
                        args.gst_launch, '-q', 'videotestsrc', 'is-live=true', f'pattern={pattern}',
                        '!', 'video/x-raw,width=640,height=360,framerate=15/1',
                        '!', 'videoconvert', '!', 'video/x-raw,format=I420',
                        '!', 'x264enc', 'tune=zerolatency', 'speed-preset=ultrafast', 'key-int-max=15',
                        '!', 'video/x-h264,profile=constrained-baseline', '!', 'h264parse',
                        '!', 'rtph264pay', 'pt=97', 'config-interval=-1',
                        '!', 'udpsink', 'host=127.0.0.1', f'port={port}', 'sync=false'], stdout=log, stderr=log)
                    senders.append(sender)
                    processes.append(sender)
                until(lambda state: all(c['fresh'] for c in state['cameras'][1:]))
                time.sleep(6)
                # The encoded recording branch must produce a playable finalized clip.
                clips=sorted((root/'rolling'/str(ports[0])).glob('*.mp4'))
                assert len(clips)>=2, 'Rolling capture did not rotate'
                subprocess.run([args.gst_launch,'-q','filesrc',f'location={clips[0]}','!',
                    'qtdemux','!','h264parse','!','vtdec_hw','!','fakesink'],check=True,timeout=8)
                stop(senders[1])
                until(lambda state: state['cameras'][1]['fresh'] and not state['cameras'][2]['fresh']
                      and not state['cameras'][2]['visible'] and state['cameras'][3]['fresh'])
                assert request('signal left')['signal']=='left'
                time.sleep(.3)
                stop(hud)
                assert hud.returncode==0, (root/'hud.log').read_text()
                subprocess.run([args.gst_launch, '-q', 'filesrc', f'location={root/"hud.png"}',
                    '!', 'pngdec', '!', 'videoconvert', '!', 'video/x-raw,format=RGB',
                    '!', 'filesink', f'location={root/"hud.rgb"}'], check=True, timeout=10)
                pixels=(root/'hud.rgb').read_bytes()
                def pixel(x,y):
                    offset=(y*640+x)*3
                    return tuple(pixels[offset:offset+3])
                red=pixel(75,250)
                assert red[0]>180 and max(red[1:])<65, ('Left signal must focus LEFT feed',red)
                assert max(pixel(300,60))<8, 'Unselected REAR feed must stay hidden'
                assert max(pixel(75,112))<8, 'LEFT must not also appear as a thumbnail'
                assert max(pixel(515,112))<8, 'Stale RIGHT image must clear to black'
                print('PASS: three feeds, independent expiry, single left-signal inset, hidden other feeds, and black stale image')
            finally:
                for process in reversed(processes):
                    stop(process)


if __name__ == '__main__':
    main()
