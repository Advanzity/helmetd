"""Paced mono RTP/L16 output to the configured helmet (48 kHz, PT 98)."""
import json
import math
import secrets
import socket
import struct
import subprocess
import tempfile
import threading
import time
import wave
from array import array
from pathlib import Path


class PiAudio:
    def __init__(self, config=Path('.local/pi-audio.json')):
        self.config = Path(config)
        self.lock = threading.Lock()
        self.generation = 0
        self.state_lock = threading.Lock()
        self.priority = 0
        self.sequence = secrets.randbits(16)
        self.timestamp = secrets.randbits(32)
        self.ssrc = secrets.randbits(32)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def target(self):
        try:
            data = json.loads(self.config.read_text())
            return socket.gethostbyname(data['host']), int(data.get('port', 5010))
        except (OSError, ValueError, KeyError):
            return None

    def cancel(self, priority=3):
        with self.state_lock:
            if self.priority <= priority:
                self.generation += 1
                self.priority = 0

    def claim(self, priority):
        with self.state_lock:
            if self.priority >= priority:
                return None
            self.generation += 1
            self.priority = priority
            return self.generation

    def release(self, generation):
        with self.state_lock:
            if self.generation == generation:
                self.priority = 0

    def play(self, pcm, volume=1, generation=None, priority=1):
        if not math.isfinite(volume) or not 0 <= volume <= 1 or len(pcm) % 2:
            raise ValueError('Invalid PCM or volume')
        target = self.target()
        if not target:
            raise ValueError('Helmet audio is not configured')
        if generation is None:
            generation = self.claim(priority)
        if generation is None or generation != self.generation:
            return False
        try:
            return self._play(pcm, volume, generation, target)
        finally:
            self.release(generation)

    def _play(self, pcm, volume, generation, target):
        with self.lock:
            deadline = time.monotonic()
            self.timestamp = int(deadline*48000) & 0xffffffff
            for offset in range(0, len(pcm), 960):
                if generation != self.generation:
                    return False
                samples = array('h', pcm[offset:offset+960])
                if volume != 1:
                    samples = array('h', (int(v*volume) for v in samples))
                payload = struct.pack('!%dh' % len(samples), *samples)
                header = struct.pack('!BBHII', 0x80, 98, self.sequence, self.timestamp, self.ssrc)
                self.socket.sendto(header+payload, target)
                self.sequence = (self.sequence+1) & 65535
                self.timestamp = (self.timestamp+len(samples)) & 0xffffffff
                deadline += len(samples)/48000
                time.sleep(max(0, deadline-time.monotonic()))
        return True

    def speak(self, text, volume=1, priority=2):
        generation = self.claim(priority)
        if generation is None:
            return False
        try:
            return self._speak(text, volume, generation)
        finally:
            self.release(generation)

    def _speak(self, text, volume, generation):
        with tempfile.TemporaryDirectory(prefix='helmet-speech-') as directory:
            output = str(Path(directory)/'cue.wav')
            subprocess.run(['say', '-o', output, '--file-format=WAVE', '--data-format=LEI16@48000', '--channels=1', '-f', '-'],
                           input=text.encode(), check=True, timeout=15, capture_output=True)
            with wave.open(output, 'rb') as wav:
                if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 48000):
                    raise ValueError('Unexpected speech format')
                pcm = wav.readframes(wav.getnframes())
            return self.play(pcm, volume, generation)


class PiPcmOutput:
    """PortAudio-compatible writer for the native 16 kHz voice session."""
    def __init__(self, speaker):
        self.speaker = speaker

    def write(self, pcm):
        samples = array('h', pcm)
        converted = array('h')
        for i, value in enumerate(samples):
            following = samples[min(i+1, len(samples)-1)]
            converted.extend((value, int((2*value+following)/3), int((value+2*following)/3)))
        self.speaker.play(converted.tobytes())

    def stop_stream(self):
        self.speaker.cancel()

    def close(self):
        self.speaker.socket.close()
