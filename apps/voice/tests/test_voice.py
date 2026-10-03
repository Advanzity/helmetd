import sys
import threading
import wave
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from helmetd_voice import voice
from helmetd_voice.audio import LocalAudio


@pytest.fixture
def tts(monkeypatch):
    for name in ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "ELEVENLABS_TTS_MODEL"):
        monkeypatch.setenv(name, "test-value")
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200, content=b"\x00\x00\x01\x00", headers={"content-type": "audio/pcm"}
        )

    # Keep the real ElevenLabs SDK and replace only its HTTP transport.
    original = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kw: original(**kw, transport=httpx.MockTransport(respond))
    )
    return requests


def test_tts_writes_valid_wave_without_microphone(tts, tmp_path):
    path = tmp_path / "alert.wav"
    voice.say("Camera ready", path)
    with wave.open(str(path), "rb") as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 16000)
        assert wav.readframes(2) == b"\x00\x00\x01\x00"
    assert len(tts) == 1
    assert tts[0].url.params["output_format"] == "pcm_16000"
    assert b'"text":"Camera ready"' in tts[0].content


def test_existing_recording_not_overwritten_or_billed(tts, tmp_path):
    path = tmp_path / "alert.wav"
    path.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        voice.say("Camera ready", path)
    assert path.read_bytes() == b"original"
    assert not tts


def test_pcm_network_chunks_preserve_samples():
    assert list(voice.pcm_frames([b"\x00", b"\x01\x02", b"", b"\x03"])) == [
        b"\x00\x01",
        b"\x02\x03",
    ]
    with pytest.raises(RuntimeError, match="truncated"):
        list(voice.pcm_frames([b"\x00"]))
    with pytest.raises(RuntimeError, match="no audio"):
        list(voice.pcm_frames([]))


def test_failed_tts_removes_partial_recording(monkeypatch, tts, tmp_path):
    def broken(_):
        yield b"\x00\x00"
        raise RuntimeError("broken stream")

    monkeypatch.setattr(voice, "pcm_frames", broken)
    path = tmp_path / "alert.wav"
    with pytest.raises(RuntimeError):
        voice.say("Camera ready", path)
    assert not path.exists()


def test_audio_partial_start_failure_releases_output(monkeypatch):
    output = Mock()
    audio = Mock()
    audio.open.side_effect = [output, OSError("no microphone")]
    module = SimpleNamespace(PyAudio=lambda: audio, paInt16=8, paContinue=0)
    monkeypatch.setitem(sys.modules, "pyaudio", module)
    interface = LocalAudio()
    with pytest.raises(RuntimeError, match="microphone"):
        interface.start(lambda _: None)
    interface.stop()
    output.close.assert_called_once()
    audio.terminate.assert_called_once()


def test_stop_before_start_does_not_open_devices(monkeypatch):
    constructor = Mock()
    monkeypatch.setitem(sys.modules, "pyaudio", SimpleNamespace(PyAudio=constructor))
    audio = LocalAudio()
    audio.stop()
    audio.start(lambda _: None)
    constructor.assert_not_called()


def test_upload_shutdown_does_not_join_itself(monkeypatch):
    device = Mock()
    device.open.side_effect = [Mock(), Mock()]
    monkeypatch.setitem(
        sys.modules, "pyaudio", SimpleNamespace(PyAudio=lambda: device, paInt16=8, paContinue=0)
    )
    audio = LocalAudio()
    ended = threading.Event()

    def shutdown(_):
        audio.stop()
        ended.set()

    audio.start(shutdown)
    audio._input_queue.put(b"\x00\x00")
    assert ended.wait(2)
    device.terminate.assert_called_once()


def test_conversation_worker_failure_is_contained_and_cleaned(monkeypatch):
    def fail(self, url):
        raise RuntimeError("signed-url-secret")

    monkeypatch.setattr(Conversation, "_run", fail)
    audio = Mock()
    # The SDK starts its client-tools worker at construction; managed shutdown must stop it.
    with httpx.Client() as http:
        conversation = voice.ManagedConversation(
            ElevenLabs(api_key="test", httpx_client=http),
            "agent-test",
            requires_auth=True,
            audio_interface=audio,
        )
        conversation._run("unused")
        conversation.end_session()
    assert conversation.error
    assert "secret" not in conversation.error
    audio.stop.assert_called_once()
