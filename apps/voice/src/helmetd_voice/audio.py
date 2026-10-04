"""Local microphone with 16 kHz PCM playback on Mac or the configured Pi HDMI link."""

import queue
import threading
import time
from array import array

from elevenlabs.conversational_ai.conversation import AudioInterface


class LocalAudio(AudioInterface):
    def __init__(self, input_enabled=True, macbook=False):
        self.input_enabled = input_enabled
        self.macbook = macbook
        self._audio = None
        self._input = None
        self._output = None
        self._thread = None
        self._send_thread = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._play_lock = threading.RLock()
        self._generation = 0
        self._alert_until = 0
        self.volume = 1.0
        self._speaking_until = 0
        self._queue = queue.Queue(maxsize=64)
        self._input_queue = queue.Queue(maxsize=8)
        self.dropped_input_chunks = 0
        self.error = None
        self.on_error = None

    def start(self, input_callback):
        import pyaudio

        try:
            with self._lock:
                if not self._stop.is_set():
                    self._start_devices(input_callback, pyaudio)
        except Exception:
            self.error = (
                "Could not open Mac microphone/output; check devices and microphone permission"
            )
            self.stop()
            raise RuntimeError(self.error) from None

    def _start_devices(self, input_callback, pyaudio):
        self._audio = pyaudio.PyAudio()
        output_options = {}
        input_options = {}
        if self.macbook:
            output_options["output_device_index"] = self._macbook_device("output", "Speakers")
            if self.input_enabled:
                input_options["input_device_index"] = self._macbook_device("input", "Microphone")
        from .pi_audio import PiAudio, PiPcmOutput
        helmet = PiAudio()
        self._output = PiPcmOutput(helmet) if helmet.target() and not self.macbook else self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            output=True,
            frames_per_buffer=1000,
            **output_options,
        )

        def record(data, *_):
            if not self._stop.is_set():
                if time.monotonic() < self._alert_until:
                    data = bytes(len(data))
                self._queue_input(data)
            return None, pyaudio.paContinue

        if self.input_enabled:
            self._input = self._audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                stream_callback=record,
                frames_per_buffer=4000,
                **input_options,
            )
        self._thread = threading.Thread(target=self._play, args=(self._output,), daemon=True)
        self._send_thread = threading.Thread(
            target=self._send,
            args=(input_callback,),
            daemon=True,
        )
        self._thread.start()
        if self.input_enabled:
            self._send_thread.start()
        else:
            self._send_thread = None

    def _macbook_device(self, direction, label):
        for index in range(self._audio.get_device_count()):
            device = self._audio.get_device_info_by_index(index)
            name = device["name"]
            if (
                name.startswith("MacBook")
                and label in name
                and device[f"max{direction.capitalize()}Channels"] > 0
            ):
                print(f"Voice {direction}: {name}", flush=True)
                return index
        raise RuntimeError(f"Built-in MacBook {direction} device is unavailable")

    def _fail(self, message):
        self.error = message
        self._stop.set()
        if self.on_error:
            self.on_error()

    def _queue_input(self, data):
        # CoreAudio and network scheduling can arrive in bursts. Keep bounded,
        # recent speech instead of terminating the conversation on backpressure.
        try:
            self._input_queue.put_nowait(data)
        except queue.Full:
            try:
                self._input_queue.get_nowait()
                self.dropped_input_chunks += 1
            except queue.Empty:
                pass  # The uploader drained it between put and get.
            self._input_queue.put_nowait(data)

    def _send(self, callback):
        # Keep network I/O and SDK shutdown off PortAudio's real-time callback.
        reported_drops = 0
        last_report = -float("inf")
        while not self._stop.is_set():
            if self.error:
                self._fail(self.error)
                return
            try:
                data = self._input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                callback(data)
                now = time.monotonic()
                if self.dropped_input_chunks > reported_drops and now - last_report >= 10:
                    print("Microphone buffer recovered; skipped older audio.", flush=True)
                    reported_drops, last_report = self.dropped_input_chunks, now
            except Exception:
                self._fail("Microphone upload failed")

    def _play(self, output):
        try:
            while not self._stop.is_set():
                try:
                    generation, audio = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                for offset in range(0, len(audio), 640):
                    if self._stop.is_set() or generation != self._generation:
                        break
                    chunk = audio[offset : offset + 640]
                    if self.volume != 1.0:
                        samples = array("h", chunk)
                        chunk = array("h", (int(s * self.volume) for s in samples)).tobytes()
                    self._speaking_until = time.monotonic() + 0.2
                    output.write(chunk)
        except Exception:
            self._fail("Audio output failed")

    def output(self, audio: bytes):
        if self.error:
            raise RuntimeError(self.error)
        with self._play_lock:
            if time.monotonic() >= self._alert_until:
                self._queue.put((self._generation, audio), timeout=1)

    def interrupt(self):
        with self._play_lock:
            self._generation += 1
            self._speaking_until = 0
            self._alert_until = 0
            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    return

    def play_alert(self, pcm):
        with self._play_lock:
            if self._output is None or self._stop.is_set():
                return False
            self.interrupt()
            self._alert_until = time.monotonic() + len(pcm) / 32000 + 0.25
            self._queue.put_nowait((self._generation, pcm))
            return True

    def cancel_alert(self):
        with self._play_lock:
            if time.monotonic() < self._alert_until:
                self.interrupt()
            else:
                self._alert_until = 0

    def stop(self):
        self._stop.set()
        with self._lock:
            threads = self._thread, self._send_thread
            streams = self._input, self._output
            audio = self._audio
            self._thread = self._send_thread = None
            self._input = self._output = self._audio = None
        for thread in threads:
            if thread and thread is not threading.current_thread():
                thread.join()
        for stream in streams:
            if stream:
                stream.stop_stream()
                stream.close()
        if audio:
            audio.terminate()

    @property
    def active(self):
        return self._input is not None and not self._stop.is_set()

    @property
    def speaking(self):
        return time.monotonic() < self._speaking_until
