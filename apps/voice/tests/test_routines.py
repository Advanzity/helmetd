import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from helmetd_voice.copilot import Copilot


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    monkeypatch.setattr("helmetd_voice.copilot.position", Mock(side_effect=ValueError))
    hud = Mock()
    state = {
        "status": "ok",
        "panels": 0,
        "diagnostics": True,
        "camera_source": "udp",
        "camera_fresh": True,
        "detection_fresh": True,
        "detections": [],
    }

    def request(command, **kwargs):
        if command.startswith("mode "):
            state["panels"] = {"full": 7, "focus": 4, "clear": 0}[command.split()[1]]
        if command == "diagnostics off":
            state["diagnostics"] = False
        return state.copy()

    hud.request.side_effect = request
    return Copilot(
        audio=SimpleNamespace(volume=0.5, active=True, speaking=False),
        listener=SimpleNamespace(enabled=False),
        directory=tmp_path,
        hud=hud,
    )


def test_suit_up_focus_and_stand_down_coordinate_real_state_and_debrief(pilot):
    result = json.loads(pilot.call("run_routine", {"routine": "suit_up"}))
    assert result["status"] == "ok"
    assert result["briefing"]["systems"]["hud"]["panels"] == 7
    assert not result["briefing"]["systems"]["hud"]["diagnostics"]
    assert pilot.listener.enabled and pilot.ride
    first_id = pilot.ride["id"]
    pilot.call("run_routine", {"routine": "suit_up"})
    assert pilot.ride["id"] == first_id
    pilot.call("save_note", {"text": "Check tyre pressure"})
    result = json.loads(pilot.call("run_routine", {"routine": "road_focus"}))
    assert result["briefing"]["systems"]["hud"]["panels"] == 4
    assert pilot.ride["id"] == first_id
    result = json.loads(pilot.call("run_routine", {"routine": "stand_down"}))
    assert result["status"] == "ok" and pilot.ride is None
    assert result["briefing"]["systems"]["hud"]["panels"] == 0
    assert result["briefing"]["last_ride"]["notes_saved"] == 1
    assert pilot.listener.enabled and pilot.audio.volume == 0.5
    assert not pilot.end_timer  # Debrief can still be spoken.
    saved = json.loads(next((pilot.directory / "rides").glob("*.json")).read_text())
    assert saved["end_reason"] == "completed" and saved["ended_at"] >= saved["started_at"]


def test_failed_hud_does_not_start_a_ride_or_claim_routine_success(pilot):
    pilot.hud.request.side_effect = None
    pilot.hud.request.return_value = {"status": "unavailable"}
    result = json.loads(pilot.call("run_routine", {"routine": "suit_up"}))
    assert result["status"] == "partial" and pilot.ride is None
    assert result["steps"][0]["result"]["status"] == "unavailable"
    assert "HUD is disconnected" in result["briefing"]["attention"]


def test_failed_step_preserves_other_acknowledgements(pilot):
    pilot.set_diagnostics = Mock(side_effect=OSError("disconnected"))
    pilot.handlers["set_diagnostics"] = pilot.set_diagnostics
    result = json.loads(pilot.call("run_routine", {"routine": "suit_up"}))
    assert result["status"] == "partial"
    assert [s["result"]["status"] for s in result["steps"]] == ["ok", "error", "ok", "ok"]


def test_briefing_is_read_only_and_prioritizes_actual_gaps(pilot):
    pilot.audio.volume = 0
    result = json.loads(pilot.call("mission_briefing"))
    assert pilot.ride is None and not pilot.listener.enabled
    assert "Spoken detection alerts are off" in result["attention"]
    assert "Voice and spoken alerts are at zero volume" in result["attention"]
    assert any("No fresh location" in i for i in result["attention"])
    pilot.hud.request.assert_called_once_with("status")


def test_unknown_routine_has_no_side_effects(pilot):
    assert (
        json.loads(pilot.call("run_routine", {"routine": "launch missiles"}))["status"] == "error"
    )
    pilot.hud.request.assert_not_called()
    assert pilot.ride is None


def test_network_context_send_does_not_block_hud_heartbeat(pilot):
    sending, release = threading.Event(), threading.Event()

    def send(_):
        sending.set()
        release.wait(3)

    pilot.on_context = send
    pilot.start()
    try:
        assert sending.wait(2)
        changed = threading.Event()
        original = pilot.hud.request.side_effect

        def request(command, **kwargs):
            if command == "phase speaking":
                changed.set()
            return original(command, **kwargs)

        pilot.hud.request.side_effect = request
        pilot.audio.speaking = True
        assert changed.wait(2)
    finally:
        release.set()
        pilot.stop()
    assert not pilot.heartbeat.is_alive() and not pilot.context_worker.is_alive()
