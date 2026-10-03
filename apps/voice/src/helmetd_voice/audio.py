"""Local 16 kHz mono PCM audio; replace this interface for a future Pi audio link."""

import queue
import threading

from elevenlabs.conversational_ai.conversation import AudioInterface


class LocalAudio(AudioInterface):
    def __init__(self):
        self._audio = None
        self._input = None
        self._output = None
        self._thread = None
        self._send_thread = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._queue = queue.Queue(maxsize=64)
        self._input_queue = queue.Queue(maxsize=8)
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
        self._output = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            output=True,
            frames_per_buffer=1000,
        )

        def record(data, *_):
            if not self._stop.is_set():
                try:
                    self._input_queue.put_nowait(data)
                except queue.Full:
                    self.error = "Microphone upload is falling behind"
            return None, pyaudio.paContinue

        self._input = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            stream_callback=record,
            frames_per_buffer=4000,
        )
        self._thread = threading.Thread(target=self._play, args=(self._output,), daemon=True)
        self._send_thread = threading.Thread(
            target=self._send,
            args=(input_callback,),
            daemon=True,
        )
        self._thread.start()
        self._send_thread.start()

    def _fail(self, message):
        self.error = message
        self._stop.set()
        if self.on_error:
            self.on_error()

    def _send(self, callback):
        # Keep network I/O and SDK shutdown off PortAudio's real-time callback.
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
            except Exception:
                self._fail("Microphone upload failed")

    def _play(self, output):
        try:
            while not self._stop.is_set():
                try:
                    audio = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                output.write(audio)
        except Exception:
            self._fail("Audio output failed")

    def output(self, audio: bytes):
        if self.error:
            raise RuntimeError(self.error)
        self._queue.put(audio, timeout=1)

    def interrupt(self):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

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
