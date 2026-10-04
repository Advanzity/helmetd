import json
import queue
import time
from unittest.mock import Mock

import pytest
from helmetd_voice.alerts import AlertGate
from helmetd_voice.audio import LocalAudio


def packet(seq=1, kind="person", sent=100000, expires=100400):
    return json.dumps(
        {
            "version": 1,
            "session": "test",
            "seq": seq,
            "kind": kind,
            "sent_at_ms": sent,
            "expires_at_ms": expires,
        }
    ).encode()


@pytest.mark.parametrize(
    "payload",
    [
        b"garbage",
        b"[]",
        b"null",
        packet(expires=102000),
        packet(sent=110000, expires=110400),
        packet(kind="brake"),
    ],
)
def test_invalid_or_future_events_never_speak(payload):
    gate, play = AlertGate(), Mock()
    assert not gate.receive(payload, 100)
    gate.tick(100, play, Mock())
    play.assert_not_called()


def test_replay_cooldown_and_expiry():
    gate, play, cancel = AlertGate(), Mock(return_value=True), Mock()
    assert gate.receive(packet(), 100)
    assert not gate.receive(packet(), 100.01)
    gate.tick(100.01, play, cancel)
    play.assert_called_once_with("person")
    assert gate.receive(packet(seq=2), 100.02)
    gate.tick(100.02, play, cancel)
    assert play.call_count == 1
    gate.tick(100.5, play, cancel)
    cancel.assert_called_once()
    gate.tick(103, play, cancel)
    assert gate.receive(packet(seq=3, sent=104000, expires=104400), 104)
    gate.tick(104, play, cancel)
    assert play.call_count == 1  # Still inside the eight-second cooldown.
    assert gate.receive(packet(seq=4, sent=109000, expires=109400), 109)
    gate.tick(109, play, cancel)
    assert play.call_count == 2


def test_audio_not_started_does_not_consume_alert():
    gate, play = AlertGate(), Mock(side_effect=[False, True])
    gate.receive(packet(), 100)
    gate.tick(100, play, Mock())
    gate.tick(100.1, play, Mock())
    assert play.call_count == 2


def test_priority_alert_clears_speech_and_suppresses_overlap():
    audio = LocalAudio(input_enabled=False)
    assert not audio.play_alert(b"\0" * 640)
    audio._output = Mock()
    audio.output(b"ordinary speech")
    assert audio.play_alert(b"\0" * 640)
    audio.output(b"overlap")
    _, clip = audio._queue.get_nowait()
    assert clip == b"\0" * 640
    with pytest.raises(queue.Empty):
        audio._queue.get_nowait()
    audio.cancel_alert()
    audio.output(b"new speech")
    assert audio._queue.get_nowait()[1] == b"new speech"


def test_finished_alert_does_not_cancel_later_conversation():
    audio = LocalAudio()
    audio._alert_until = time.monotonic() - 1
    audio.output(b"new speech")
    audio.cancel_alert()
    assert audio._queue.get_nowait()[1] == b"new speech"


def test_interrupt_stops_inflight_audio_after_one_chunk():
    audio = LocalAudio()
    output = Mock()
    audio.output(bytes(6400))

    def write(_):
        audio.interrupt()
        audio._stop.set()

    output.write.side_effect = write
    audio._play(output)
    output.write.assert_called_once_with(bytes(640))
