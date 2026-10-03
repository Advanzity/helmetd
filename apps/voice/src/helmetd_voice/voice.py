import os
import threading
import wave
from contextlib import contextmanager
from pathlib import Path

import httpx
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation

from .audio import LocalAudio


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Set {name} in your environment or local .env")
    return value


@contextmanager
def elevenlabs_client():
    key = required("ELEVENLABS_API_KEY")
    with httpx.Client(timeout=30) as http:
        yield ElevenLabs(api_key=key, httpx_client=http)


class ManagedConversation(Conversation):
    """Contain worker errors and close audio even if WebSocket startup fails.

    The pinned SDK exposes no worker-error callback; this is the sole private
    hook. Its lifecycle is covered by an offline test when updating the SDK.
    """

    error = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._end_lock = threading.Lock()
        self._ended = False

    def end_session(self):
        # The SDK can request shutdown from both the audio and WebSocket threads.
        with self._end_lock:
            if self._ended:
                return
            self._ended = True
        super().end_session()

    def _run(self, ws_url):
        try:
            super()._run(ws_url)
        except Exception:
            self.error = "Voice session failed; check the agent, connection, and audio devices"
        finally:
            self.end_session()


def talk():
    agent_id = required("ELEVENLABS_AGENT_ID")
    audio = LocalAudio()
    with elevenlabs_client() as client:
        conversation = ManagedConversation(
            client,
            agent_id,
            requires_auth=True,
            audio_interface=audio,
            callback_agent_response=lambda text: print(f"Helmetd: {text}", flush=True),
            callback_user_transcript=lambda text: print(f"You: {text}", flush=True),
            callback_agent_response_correction=lambda original, corrected: print(
                f"Helmetd (corrected): {corrected}", flush=True
            ),
        )
        audio.on_error = conversation.end_session
        started = False
        try:
            conversation.start_session()
            started = True
            print("Voice session starting. Press Ctrl-C to stop.", flush=True)
            conversation_id = conversation.wait_for_session_end()
        except KeyboardInterrupt:
            conversation.end_session()
            conversation_id = conversation.wait_for_session_end() if started else None
        finally:
            conversation.end_session()
        if conversation.error or audio.error:
            raise RuntimeError(conversation.error or audio.error)
        if conversation_id:
            print(f"Conversation: {conversation_id}")


def pcm_frames(chunks):
    """SDK/network boundaries need not coincide with 16-bit sample boundaries."""
    remainder = b""
    saw_samples = False
    for chunk in chunks:
        data = remainder + chunk
        end = len(data) - len(data) % 2
        if end:
            saw_samples = True
            yield data[:end]
        remainder = data[end:]
    if remainder:
        raise RuntimeError("ElevenLabs returned a truncated PCM sample")
    if not saw_samples:
        raise RuntimeError("ElevenLabs returned no audio")


def say(text: str, output: Path | None = None):
    if not text.strip():
        raise ValueError("Alert text cannot be empty")
    voice_id = required("ELEVENLABS_VOICE_ID")
    model_id = required("ELEVENLABS_TTS_MODEL")
    with elevenlabs_client() as client:
        chunks = client.text_to_speech.stream(
            voice_id=voice_id,
            text=text,
            model_id=model_id,
            output_format="pcm_16000",
        )
        try:
            if output:
                # Exclusive creation prevents accidentally replacing recordings.
                created = False
                try:
                    with output.open("xb") as file:
                        created = True
                        with wave.open(file, "wb") as wav:
                            wav.setnchannels(1)
                            wav.setsampwidth(2)
                            wav.setframerate(16000)
                            for data in pcm_frames(chunks):
                                wav.writeframesraw(data)
                except BaseException:
                    if created:
                        output.unlink(missing_ok=True)
                    raise
            else:
                import pyaudio

                audio = pyaudio.PyAudio()
                stream = None
                try:
                    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000, output=True)
                    for data in pcm_frames(chunks):
                        stream.write(data)
                finally:
                    if stream:
                        stream.stop_stream()
                        stream.close()
                    audio.terminate()
        finally:
            chunks.close()
