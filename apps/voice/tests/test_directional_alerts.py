from helmetd_voice.directional_alerts import DirectionalAlerts


def scene(side='LEFT', label='CAR', fresh=True):
    return {'status': 'ok', 'cameras': [{'label': side, 'fresh': fresh,
        'detection_fresh': fresh, 'detections': [{'label': label, 'image_region': 'center'}]}]}


def test_direction_persistence_and_no_repeated_speech():
    gate = DirectionalAlerts()
    assert gate.update(scene(), 0) is None
    key = gate.update(scene(), .5)
    assert gate.phrase(key) == 'Vehicle detected on the left.'
    gate.mark_spoken(key, .5)
    assert gate.update(scene(), 1) is None
    assert gate.update(scene(), 10) is None
    gate.update({'status': 'unavailable'}, 13)
    assert gate.update(scene(), 14) is None
    assert gate.update(scene(), 14.5) == key
    assert gate.phrase(('right', 'CAR')) == 'Car detected on the right.'
    assert gate.phrase(('front', 'PERSON')) == 'Person detected.'


def test_stale_muted_and_global_cooldown_do_not_speak():
    gate = DirectionalAlerts()
    gate.update(scene(), 0)
    assert gate.update(scene(fresh=False), .5) is None
    gate.enabled = False
    assert gate.update(scene(), .6) is None
    gate.enabled = True
    gate.mark_spoken(('front','PERSON'), 1)
    gate.update(scene('RIGHT'), 1.5)
    assert gate.update(scene('RIGHT'), 2) is None


def test_brief_inference_gap_does_not_restart_confirmation():
    gate = DirectionalAlerts()
    assert gate.update(scene(), 0) is None
    gap = scene(); gap['cameras'][0]['detection_fresh'] = False
    assert gate.update(gap, .4) is None
    assert gate.update(scene(), .9) == ('left', 'VEHICLE')
    assert gate.update(scene(fresh=False), 1) is None


def test_vehicle_class_change_does_not_repeat_event():
    gate = DirectionalAlerts()
    gate.update(scene(label='CAR'), 0)
    key = gate.update(scene(label='TRUCK'), .6)
    assert key == ('left', 'VEHICLE')
    gate.mark_spoken(key, .6)
    assert gate.update(scene(label='BUS'), 6) is None


def test_disconnect_requires_new_confirmation():
    gate = DirectionalAlerts()
    gate.update(scene(), 0)
    assert gate.update(scene(fresh=False), .4) is None
    assert gate.update(scene(), .6) is None
    assert gate.update(scene(), 1.2) == ('left', 'VEHICLE')


def test_rear_vehicle_and_front_person_priority():
    gate = DirectionalAlerts()
    state = scene('REAR')
    state['cameras'] += scene('FRONT', 'PERSON')['cameras']
    gate.update(state, 0)
    assert gate.update(state, .6) == ('front', 'PERSON')
    gate.mark_spoken(('front', 'PERSON'), .6)
    for at in (1, 2, 3, 4):
        assert gate.update(state, at) is None
    assert gate.update(state, 5) == ('rear', 'VEHICLE')
    assert gate.phrase(('rear', 'VEHICLE')) == 'Vehicle detected behind you.'
