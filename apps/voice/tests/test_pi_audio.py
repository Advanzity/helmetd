import json
import socket
import struct
from array import array

from helmetd_voice.pi_audio import PiAudio, PiPcmOutput


def test_rtp_pcm_byte_order_volume_timestamp_and_cancellation(tmp_path):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(('127.0.0.1', 0))
        receiver.settimeout(.2)
        config = tmp_path/'audio.json'
        config.write_text(json.dumps({'host': '127.0.0.1', 'port': receiver.getsockname()[1]}))
        sender = PiAudio(config)
        pcm = array('h', [12000, -12000]*480).tobytes()
        assert sender.play(pcm, .5)
        packets = [receiver.recv(1500), receiver.recv(1500)]
        headers = [struct.unpack('!BBHII', p[:12]) for p in packets]
        assert headers[0][:2] == (128, 98)
        assert (headers[1][2]-headers[0][2]) & 65535 == 1
        assert (headers[1][3]-headers[0][3]) & 0xffffffff == 480
        assert struct.unpack('!hh', packets[0][12:16]) == (6000, -6000)
        generation = sender.generation
        sender.cancel()
        assert not sender.play(pcm, generation=generation)
        sender.socket.close()


def test_native_rate_conversion_preserves_duration():
    class Speaker:
        def play(self, data):
            self.data = data
    speaker = Speaker()
    PiPcmOutput(speaker).write(array('h', [1000]*320).tobytes())
    assert len(speaker.data) == 960*2
    assert set(array('h', speaker.data)) == {1000}


def test_audio_priority_preempts_lower_sources_and_scopes_cancel(tmp_path):
    speaker = PiAudio(tmp_path/'absent.json')
    conversation = speaker.claim(1)
    navigation = speaker.claim(2)
    assert navigation != conversation
    assert speaker.claim(1) is None
    alert = speaker.claim(3)
    assert alert != navigation
    speaker.cancel(1)
    assert speaker.generation == alert
    speaker.cancel(2)
    assert speaker.generation == alert
    speaker.release(navigation)
    assert speaker.priority == 3
    speaker.release(alert)
    assert speaker.claim(1) is not None
    speaker.socket.close()
