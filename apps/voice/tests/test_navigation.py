from unittest.mock import Mock

import pytest
from helmetd_voice.navigation import NODES, PLACES, Navigation, route_between


def start(nav, destination="lookout", preference="fastest"):
    nav.plan({"destination": destination, "preference": preference})
    return nav.control({"action": "start"})


def finish(nav):
    for _ in range(20):
        if nav.state == "arrived":
            return nav.snapshot()
        if nav.state == "paused":
            nav.control({"action": "resume"})
        nav.demo({"event": "next_turn"})
    raise AssertionError("Route did not arrive")


@pytest.mark.parametrize("destination", PLACES)
@pytest.mark.parametrize("preference", ["fastest", "avoid_highways"])
def test_routes_reach_their_destination(destination, preference):
    nav = Navigation()
    start(nav, destination, preference)
    result = finish(nav)
    assert result["location"] == NODES[destination]
    assert result["remaining_m"] == result["remaining_s"] == 0
    assert result["next_turn"] is None
    assert result["source"] == "simulation" and not result["playing"]


def test_highway_preference_changes_the_actual_path_and_time():
    fastest = route_between(NODES["garage"], "lookout", "fastest")
    local = route_between(NODES["garage"], "lookout", "avoid_highways")
    assert any(leg["street"] == "Expressway" for leg in fastest)
    assert all(leg["street"] != "Expressway" for leg in local)
    assert sum(leg["duration_s"] for leg in fastest) < sum(leg["duration_s"] for leg in local)


def test_preview_does_not_replace_active_route_and_accept_recalculates_from_position():
    nav = Navigation()
    start(nav)
    nav._advance(500)
    preview = nav.plan({"destination": "cafe"})
    assert preview["route"]["destination_id"] == "lookout"
    assert preview["preview"]["destination_id"] == "cafe"
    nav._advance(100)
    origin = nav.location
    accepted = nav.control({"action": "start"})
    assert accepted["route"]["legs"][0]["a"] == pytest.approx(origin)
    assert accepted["route"]["destination_id"] == "cafe" and accepted["preview"] is None
    assert nav.progress == 0
    # A repeated Start cannot rewind a running route.
    nav._advance(50)
    nav.control({"action": "start"})
    assert nav.progress == pytest.approx(50)


def test_unknown_addresses_do_not_replace_a_real_demo_selection():
    nav = Navigation()
    start(nav)
    before = nav.snapshot()
    with pytest.raises(ValueError, match="Real place search"):
        nav.plan({"destination": "1600 Pennsylvania Avenue"})
    assert nav.snapshot() == before


def test_added_stop_is_previewed_then_pauses_once_before_final_destination():
    nav = Navigation()
    start(nav)
    pending = nav.stop({"action": "add", "place": "fuel"})
    assert pending["route"]["stop_id"] is None
    assert pending["preview"]["stop_id"] == "fuel"
    nav.control({"action": "start"})
    for _ in range(10):
        if nav.state == "paused":
            break
        nav.demo({"event": "next_turn"})
    assert nav.state == "paused" and nav.location == NODES["fuel"]
    assert nav.route["stop_id"] is None
    assert finish(nav)["route"]["destination_id"] == "lookout"


def test_remove_stop_and_dismiss_preview_leave_active_navigation_unchanged():
    nav = Navigation()
    start(nav)
    nav.stop({"action": "add", "place": "fuel"})
    nav.control({"action": "start"})
    nav.stop({"action": "remove", "place": ""})
    assert nav.preview["stop_id"] is None and nav.route["stop_id"] == "fuel"
    nav.control({"action": "cancel_preview"})
    assert nav.preview is None and nav.route["stop_id"] == "fuel"


def test_lost_location_hides_guidance_and_requires_explicit_resume():
    now = [0.0]
    nav = Navigation(clock=lambda: now[0])
    start(nav)
    nav.demo({"event": "play"})
    now[0] += 0.5
    nav.tick()
    before = nav.location
    lost = nav.demo({"event": "lose_location"})
    assert lost["next_turn"] is lost["remaining_m"] is lost["remaining_s"] is None
    assert lost["location"] is None
    now[0] += 1
    nav.tick()
    assert nav.location == before
    with pytest.raises(ValueError):
        nav.control({"action": "resume"})
    nav.demo({"event": "restore_location"})
    assert nav.state == "paused" and not nav.playing
    nav.control({"action": "resume"})
    assert nav.snapshot()["next_turn"] is not None


def test_missed_turn_reroutes_from_new_position_and_loss_does_not_restore_old_route():
    nav = Navigation()
    start(nav)
    missed = nav.demo({"event": "miss_turn"})
    assert missed["next_turn"] is None and missed["remaining_s"] is None
    nav.demo({"event": "lose_location"})
    nav.demo({"event": "restore_location"})
    assert nav.state == "off_route"
    origin = nav.location
    rerouted = nav.control({"action": "reroute"})
    assert rerouted["route"]["legs"][0]["a"] == origin
    assert finish(nav)["state"] == "arrived"


def test_auto_movement_stops_when_console_is_abandoned_and_pause_cancel_work():
    now = [0.0]
    nav = Navigation(clock=lambda: now[0])
    start(nav)
    nav.demo({"event": "play"})
    now[0] = 1
    nav.tick()
    assert nav.progress > 0
    before = nav.location
    now[0] = 10
    nav.tick()
    assert nav.location == before and not nav.playing
    nav.control({"action": "pause"})
    with pytest.raises(ValueError):
        nav.demo({"event": "next_turn"})
    nav.control({"action": "cancel"})
    assert nav.state == "idle" and nav.route is None and nav.preview is None


def test_snapshot_is_detached_and_missing_hud_is_reported_honestly():
    nav = Navigation()
    hud = Mock()
    hud.request.return_value = {"status": "unavailable"}
    nav.action("plan", {"destination": "lookout"}, hud)
    result = nav.action("control", {"action": "start"}, hud)
    assert result["state"] == "navigating" and result["hud"]["status"] == "unavailable"
    snapshot = nav.snapshot()
    snapshot["route"]["legs"].clear()
    assert nav.route["legs"]
    command = hud.request.call_args.args[0]
    assert command.startswith("nav navigating ") and len(command.encode()) < 210
    assert "location" not in nav.summary()
