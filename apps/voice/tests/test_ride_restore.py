import json
from helmetd_voice.nearby import NearbyNavigation
from helmetd_voice.ride_restore import RideRestore


def test_restart_restores_route_paused_without_restoring_location(tmp_path):
    nav = NearbyNavigation()
    nav.route = {'geometry': [[42., -83.], [42.01, -83.01]]}
    nav.state = 'paused'
    nav.fix = {'point': [42., -83.], 'accuracy_m': 5, 'timestamp_ms': 1, 'received': 0}
    store = RideRestore(tmp_path/'ride.json')
    store.save(nav)
    content=json.loads(store.path.read_text())
    assert 'fix' not in content['navigation']
    restored=NearbyNavigation()
    assert store.restore(restored)
    assert restored.route==nav.route and restored.state=='paused' and restored.fix is None
    assert store.path.stat().st_mode & 0o777 == 0o600
    content['saved_at']=0
    store.path.write_text(json.dumps(content))
    assert not RideRestore(store.path).restore(NearbyNavigation())


def test_cancellation_clears_saved_route(tmp_path):
    store=RideRestore(tmp_path/'ride.json')
    nav=NearbyNavigation()
    store.save(nav)
    restored=NearbyNavigation()
    store.restore(restored)
    assert restored.route is None and restored.state=='idle'
