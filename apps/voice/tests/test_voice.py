import json
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
    monkeypatch.setattr("helmetd_voice.pi_audio.PiAudio.target", lambda _: None)
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


def test_macbook_mode_selects_built_in_audio_instead_of_glasses(monkeypatch):
    device = Mock()
    device.get_device_count.return_value = 3
    device.get_device_info_by_index.side_effect = [
        {"name": "XREAL 1S", "maxOutputChannels": 2},
        {"name": "MacBook Air Speakers", "maxOutputChannels": 2},
        {"name": "XREAL 1S", "maxInputChannels": 2},
        {"name": "MacBook Air Speakers", "maxInputChannels": 0},
        {"name": "MacBook Air Microphone", "maxInputChannels": 1},
    ]
    monkeypatch.setitem(
        sys.modules, "pyaudio", SimpleNamespace(PyAudio=lambda: device, paInt16=8, paContinue=0)
    )
    audio = LocalAudio(macbook=True)
    try:
        audio.start(lambda _: None)
        assert device.open.call_args_list[0].kwargs["output_device_index"] == 1
        assert device.open.call_args_list[1].kwargs["input_device_index"] == 2
    finally:
        audio.stop()


def test_macbook_mode_never_silently_falls_back_to_other_devices(monkeypatch):
    device = Mock()
    device.get_device_count.return_value = 1
    device.get_device_info_by_index.return_value = {"name": "XREAL 1S", "maxOutputChannels": 2}
    monkeypatch.setitem(
        sys.modules, "pyaudio", SimpleNamespace(PyAudio=lambda: device, paInt16=8, paContinue=0)
    )
    with pytest.raises(RuntimeError, match="Mac microphone/output"):
        LocalAudio(macbook=True).start(lambda _: None)
    device.open.assert_not_called()
    device.terminate.assert_called_once()


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


def test_microphone_backpressure_keeps_recent_audio_and_session_alive():
    audio = LocalAudio()
    entered, release, delivered = threading.Event(), threading.Event(), threading.Event()
    received = []

    def upload(data):
        received.append(data)
        if data == b"first":
            entered.set()
            release.wait(2)
        if data == b"last":
            delivered.set()

    audio._send_thread = threading.Thread(target=audio._send, args=(upload,))
    audio._send_thread.start()
    try:
        audio._queue_input(b"first")
        assert entered.wait(2)
        for i in range(20):
            audio._queue_input(bytes([i]))
        audio._queue_input(b"last")
        assert audio._input_queue.qsize() == 8
        assert audio.dropped_input_chunks == 13
        assert audio.error is None and not audio._stop.is_set()
        release.set()
        assert delivered.wait(2)
        assert received == [b"first", *[bytes([i]) for i in range(13, 20)], b"last"]
    finally:
        release.set()
        audio.stop()


def test_cli_shows_safe_session_error_instead_of_generic_message(monkeypatch, capsys):
    from helmetd_voice import cli

    monkeypatch.setattr(sys, "argv", ["helmetd-voice", "talk", "--no-sync"])
    monkeypatch.setattr(
        cli, "talk", Mock(side_effect=voice.VoiceSessionError("Audio output failed"))
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    assert "Voice session ended: Audio output failed" in capsys.readouterr().err


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


def test_context_uses_sdk_background_event_not_user_turn():
    with httpx.Client() as http:
        conversation = voice.ManagedConversation(
            ElevenLabs(api_key="test", httpx_client=http),
            "agent-test",
            requires_auth=True,
            audio_interface=Mock(),
        )
        socket = Mock()
        conversation._ws = socket
        try:
            conversation.send_contextual_update("HUD is in focus mode")
            event = json.loads(socket.send.call_args.args[0])
            assert event == {"type": "contextual_update", "text": "HUD is in focus mode"}
        finally:
            conversation.end_session()
