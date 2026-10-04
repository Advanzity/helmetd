"""Bounded local detection cues. The only cloud work is preparing fixed phrases."""

import hashlib
import json
import math
import socket
import threading
import time
import wave
from pathlib import Path

PHRASES = {
    "person": "Person in view. Check your surroundings.",
    "vehicle": "Vehicle in view. Check your surroundings.",
}
CACHE = Path(".local/voice")


def prepare_alerts(directory=CACHE):
    from .voice import required, say

    voice = required("ELEVENLABS_VOICE_ID")
    model = required("ELEVENLABS_TTS_MODEL")
    directory.mkdir(parents=True, exist_ok=True)
    clips = {}
    for kind, text in PHRASES.items():
        digest = hashlib.sha256(f"{voice}/{model}/{text}".encode()).hexdigest()[:16]
        path = directory / f"{kind}-{digest}.wav"
        if not path.exists():
            say(text, path)
        with wave.open(str(path), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
                raise ValueError(f"Invalid alert audio: {path}")
            if not 0 < wav.getnframes() <= 16000 * 8:
                raise ValueError(f"Invalid alert duration: {path}")
            clips[kind] = wav.readframes(wav.getnframes())
    return clips


class AlertGate:
    """Reject expired/replayed packets; one cue per kind until two seconds clear."""

    def __init__(self):
        self.sequences = {}
        self.kind = "none"
        self.expires = 0
        self.clear_since = None
        self.announced = set()
        self.last_play = -math.inf

    def receive(self, payload, now):
        try:
            data = json.loads(payload)
            session, seq = data["session"], data["seq"]
            sent, expires = data["sent_at_ms"], data["expires_at_ms"]
            kind = data["kind"]
            if (
                data["version"] != 1
                or kind not in {*PHRASES, "none"}
                or not isinstance(session, str)
                or not 1 <= len(session) <= 80
                or type(seq) is not int
                or seq < 0
                or type(sent) is not int
                or type(expires) is not int
                or not now * 1000 - 500 <= sent <= now * 1000 + 50
                or not sent <= expires <= sent + 500
                or (kind != "none" and expires <= now * 1000)
            ):
                return False
            previous = self.sequences.get(session, (-1, 0))
            if seq <= previous[0]:
                return False
            self.sequences = {k: v for k, v in self.sequences.items() if v[1] > now - 2}
            if len(self.sequences) >= 32 and session not in self.sequences:
                return False
            self.sequences[session] = seq, now
            self.kind, self.expires = kind, expires / 1000
            return True
        except (ValueError, TypeError, KeyError):
            return False

    def tick(self, now, play, cancel):
        if self.kind == "none" or now >= self.expires:
            cancel()
            if self.clear_since is None:
                self.clear_since = now
            if now - self.clear_since >= 2:
                self.announced.clear()
            return
        self.clear_since = None
        if self.kind not in self.announced and now - self.last_play >= 8:
            if play(self.kind):
                self.announced.add(self.kind)
                self.last_play = now


class AlertListener:
    def __init__(self, audio, clips, port=8014):
        self.audio, self.clips = audio, clips
        self.enabled = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(("127.0.0.1", port))
            self.socket.settimeout(0.05)
        except BaseException:
            self.socket.close()
            raise
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()
        print("Detection voice alerts listening on localhost.", flush=True)

    def _run(self):
        gate = AlertGate()
        while not self.stop_event.is_set():
            try:
                payload, _ = self.socket.recvfrom(4097)
                if len(payload) <= 4096:
                    gate.receive(payload, time.time())
            except TimeoutError:
                pass
            gate.tick(
                time.time(),
                lambda k: self.enabled and self.audio.play_alert(self.clips[k]),
                self.audio.cancel_alert,
            )

    def stop(self):
        self.stop_event.set()
        if self.thread.ident:
            self.thread.join()
        self.socket.close()
        self.audio.cancel_alert()


def run_alerts(port=8014):
    from .audio import LocalAudio

    clips = prepare_alerts()
    audio = LocalAudio(input_enabled=False)
    listener = AlertListener(audio, clips, port)
    try:
        audio.start(None)
        listener.start()
        while not audio.error:
            time.sleep(0.1)
        raise RuntimeError(audio.error)
    finally:
        listener.stop()
        audio.stop()
