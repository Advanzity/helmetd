import copy
import json
from unittest.mock import Mock

import pytest
from helmetd_voice.maps import distance
from helmetd_voice.nearby import NearbyNavigation


@pytest.fixture
def nearby():
    clock = [1000.0]
    place = {
        "id": "osm-node-1",
        "name": "Test cafe",
        "point": [0.002, 0.0],
        "address": "Test street",
        "distance_m": 222,
        "category": "coffee",
    }
    geometry = [[0.0, 0.0], [0.001, 0.0], [0.002, 0.0]]
    route = {
        "destination": place["name"],
        "destination_id": place["id"],
        "destination_place": place,
        "stop_place": None,
        "origin": geometry[0],
        "geometry": geometry,
        "cumulative": [distance(geometry[0], p) for p in geometry],
        "preference": "fastest",
        "duration_s": 60,
        "distance_m": 222,
        "has_highway": False,
        "has_toll": False,
        "provider": "test",
        "traffic_aware": False,
        "maneuvers": [
            {"begin": 1, "end": 1, "type": 15, "instruction": "Turn left.", "stop": False},
            {"begin": 2, "end": 2, "type": 4, "instruction": "Arrive.", "stop": False},
        ],
    }
    provider = Mock()
    provider.search.return_value = [place]
    provider.route.side_effect = lambda *args: copy.deepcopy(route)
    nav = NearbyNavigation(maps=provider, clock=lambda: clock[0], wall=lambda: clock[0])

    def fix(lat=0.0, lon=0.0, accuracy=10):
        clock[0] += 1
        return nav.location(
            {"lat": lat, "lon": lon, "accuracy_m": accuracy, "timestamp_ms": clock[0] * 1000}
        )

    def start():
        fix()
        nav.search({"query": "coffee"})
        nav.plan({"destination": place["id"]})
        nav.control({"action": "start"})

    return nav, clock, provider, fix, start


def test_real_nearby_needs_location_and_an_actual_search_result(nearby):
    nav, _, provider, fix, _ = nearby
    with pytest.raises(ValueError, match="location"):
        nav.search({"query": "coffee"})
    provider.search.assert_not_called()
    fix()
    with pytest.raises(ValueError, match="Search"):
        nav.plan({"destination": "invented place"})
    provider.route.assert_not_called()
    nav.search({"query": "coffee"})
    result = nav.plan({"destination": "osm-node-1"})
    assert result["source"] == "real" and result["preview"]
    assert nav.snapshot()["route"] is None
    assert not any(key in json.dumps(result) for key in ('"point"', '"origin"', '"geometry"'))


def test_stale_or_inaccurate_location_never_repeats_old_turns(nearby):
    nav, clock, _, fix, start = nearby
    start()
    assert nav.snapshot()["next_turn"]
    clock[0] += 16
    assert nav.snapshot()["state"] == "location_lost"
    assert nav.snapshot()["next_turn"] is None
    fix(accuracy=100)
    assert nav.snapshot()["state"] == "location_lost"
    fix()
    assert nav.snapshot()["state"] == "paused"
    assert nav.snapshot()["next_turn"] is None
    nav.control({"action": "resume"})
    assert nav.snapshot()["next_turn"]
    nav.clear_location()
    assert nav.snapshot()["next_turn"] is None


def test_outlier_suspends_cues_and_off_route_requires_distinct_fixes(nearby):
    nav, _, _, fix, start = nearby
    start()
    fix(lon=0.01)
    assert nav.snapshot()["next_turn"] is None
    nav.control({"action": "pause"})
    nav.control({"action": "resume"})
    assert nav.snapshot()["state"] == "navigating"
    fix(lon=0.01)
    assert nav.snapshot()["state"] == "off_route"
    assert nav.snapshot()["remaining_m"] is None


def test_arrival_needs_two_distinct_fixes_not_repeated_resume(nearby):
    nav, _, _, fix, start = nearby
    start()
    fix(lat=0.002)
    nav.control({"action": "pause"})
    nav.control({"action": "resume"})
    assert nav.snapshot()["state"] == "navigating"
    fix(lat=0.002)
    assert nav.snapshot()["state"] == "arrived"
    assert nav.snapshot()["remaining_m"] == 0


def test_cancel_discards_inflight_route_and_live_hud_is_not_simulated(nearby):
    nav, _, provider, _, start = nearby
    start()
    hud = Mock()
    nav.publish(hud)
    assert hud.request.call_args.args[0].startswith("nav_live navigating")
    original_route = copy.deepcopy(nav.snapshot()["route"])

    def delayed_route(*args):
        nav.control({"action": "cancel"})
        return original_route

    provider.route.side_effect = delayed_route
    with pytest.raises(ValueError, match="superseded"):
        nav.plan({"destination": "osm-node-1"})
    assert nav.snapshot()["preview"] is None and nav.snapshot()["route"] is None


def test_repeat_and_reroute_have_stable_identifiers_for_spoken_guidance(nearby):
    nav, _, _, _, start = nearby
    start()
    first = nav.snapshot()
    repeated = nav.control({"action": "repeat"})
    assert repeated["repeat_serial"] == first["repeat_serial"] + 1
    assert repeated["next_turn"]["id"] == first["next_turn"]["id"]
    rerouted = nav.control({"action": "reroute"})
    assert rerouted["route_reason"] == "rerouted"
    assert rerouted["route_generation"] == first["route_generation"] + 1


def test_mcdonalds_search_uses_restaurant_brand_not_street_geocoder():
    from helmetd_voice.maps import Maps
    from unittest.mock import Mock
    maps = Maps()
    maps.request = Mock(return_value={"elements": []})
    maps.search("McDonald's", [42.3, -83.2])
    args, kwargs = maps.request.call_args
    assert args[0] == "POST"
    assert '["amenity"="fast_food"]' in kwargs["form"]["data"]
    assert '["brand"~"McDonald",i]' in kwargs["form"]["data"]
