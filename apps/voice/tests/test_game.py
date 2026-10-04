import pytest
from helmetd_voice.game import GameBridge, GamePacket

class Hud:
    def __init__(self): self.commands = []
    def request(self, command):
        self.commands.append(command)
        return {'status':'ok'}

def packet(**changes):
    data=dict(session='ride',sequence=1,paused=False,speed_mps=10,gear=2,rpm=4000,
              signal='left',crashed=False,warnings=['left','rear'])
    return GamePacket(**(data | changes))

def test_game_bridge_order_and_pause():
    hud=Hud();bridge=GameBridge(hud)
    assert bridge.publish(packet())['source']=='game'
    assert hud.commands[-1]=='game 1 22 2 4000 left 0 5'
    with pytest.raises(ValueError): bridge.publish(packet())
    bridge.publish(packet(sequence=2,paused=True,crashed=True))
    assert hud.commands[-1]=='game 0 22 2 4000 off 0 0'
    bridge.publish(packet(session='reset'))
    with pytest.raises(ValueError): bridge.publish(packet(sequence=3))

@pytest.mark.parametrize('changes',[{'speed_mps':float('nan')},{'gear':7},
 {'warnings':['unknown']},{'signal':'left\ngame'},{'rpm':float('inf')}])
def test_invalid_values(changes):
    with pytest.raises(ValueError): packet(**changes)
