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
    assert [c for c in hud.commands if c.startswith('game ')][-1]=='game 1 22 2 4000 left 0 5'
    with pytest.raises(ValueError): bridge.publish(packet())
    bridge.publish(packet(sequence=2,paused=True,crashed=True))
    assert [c for c in hud.commands if c.startswith('game ')][-1]=='game 0 22 2 4000 off 0 0'
    bridge.publish(packet(session='reset'))
    with pytest.raises(ValueError): bridge.publish(packet(sequence=3))

@pytest.mark.parametrize('changes',[{'speed_mps':float('nan')},{'gear':7},
 {'warnings':['unknown']},{'signal':'left\ngame'},{'rpm':float('inf')}])
def test_invalid_values(changes):
    with pytest.raises(ValueError): packet(**changes)


def test_game_navigation_publishes_game_route_and_reverse_gear():
    hud=Hud();bridge=GameBridge(hud)
    nav=dict(state='navigating',maneuver='left',distance_m=100,remaining_m=500,
             destination='Michigan Avenue',points=[[0,0],[500,1000]],position=[20,30])
    bridge.publish(packet(gear=-1,navigation=nav))
    assert hud.commands[0].startswith('game 1 22 -1')
    assert any(c.startswith('game_nav navigating left 100 500') for c in hud.commands)
    assert 'nav_map active 20 30 2 0 0 500 1000' in hud.commands
    assert bridge.owns_navigation()


def test_navigation_ownership_expires():
    now=[0];bridge=GameBridge(Hud(),clock=lambda:now[0])
    bridge.publish(packet());now[0]=2
    assert not bridge.owns_navigation()


def test_inactive_tab_cannot_replace_active_ride_but_new_active_ride_can():
    bridge=GameBridge(Hud())
    bridge.publish(packet())
    with pytest.raises(ValueError): bridge.publish(packet(session='background',paused=True))
    bridge.publish(packet(session='active-tab',sequence=20))
    with pytest.raises(ValueError): bridge.publish(packet(sequence=2))
