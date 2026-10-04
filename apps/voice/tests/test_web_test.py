from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from helmetd_voice import web_test
from helmetd_voice.copilot import Copilot
from helmetd_voice.navigation import Navigation
from helmetd_voice.tool_specs import TOOLS


@pytest.fixture
def web(tmp_path, monkeypatch):
    (tmp_path / "dist").mkdir()
    (tmp_path / "index.html").write_text("TOKEN __HELMETD_TOKEN__")
    monkeypatch.setattr(web_test, "WEB", tmp_path)
    pilots = []

    def create_pilot(**kwargs):
        hud = Mock()
        hud.request.return_value = {"status": "ok", "panels": 4}
        pilot = Copilot(directory=tmp_path / "saved", hud=hud, **kwargs)
        pilot.start = Mock()
        pilot.stop = Mock(wraps=pilot.stop)
        pilots.append(pilot)
        return pilot

    token = Mock(return_value="ephemeral-session-token")
    nav_hud = Mock()
    nav_hud.path = tmp_path / "hud.sock"
    nav_hud.request.return_value = {"status": "ok"}
    app = web_test.create_web_app(token, create_pilot, navigation=Navigation(), hud=nav_hud)
    with TestClient(app, base_url="http://127.0.0.1:8016") as client:
        guard = client.get("/").text.split()[1]
        headers = {"Origin": "http://127.0.0.1:8016", "X-Helmetd": guard}
        yield SimpleNamespace(client=client, headers=headers, token=token, pilots=pilots, map_path=tmp_path / "hud-map.bgra")


def test_browser_session_is_origin_guarded_and_does_not_expose_api_key(web):
    assert web.client.post("/api/start").status_code == 403
    assert (
        web.client.post(
            "/api/start", headers={**web.headers, "Origin": "https://other-site.example"}
        ).status_code
        == 403
    )
    web.token.assert_not_called()
    response = web.client.post("/api/start", headers=web.headers)
    assert response.status_code == 200
    assert set(response.json()) == {"token", "session", "tools"}
    assert set(response.json()["tools"]) == {tool["name"] for tool in TOOLS}
    assert response.headers["cache-control"] == "no-store"
    assert web.client.get("/", headers={"Host": "attacker.example"}).status_code == 400


def test_one_active_browser_owns_actions_and_shutdown(web):
    data = web.client.post("/api/start", headers=web.headers).json()
    assert web.client.post("/api/start", headers=web.headers).status_code == 409
    assert (
        web.client.post(
            "/api/action",
            headers=web.headers,
            json={"name": "ride_session", "parameters": {"action": "start"}},
        ).status_code
        == 409
    )
    headers = {**web.headers, "X-Helmetd-Session": data["session"]}
    response = web.client.post(
        "/api/action",
        headers=headers,
        json={"name": "ride_session", "parameters": {"action": "start"}},
    )
    assert response.json()["result"]["started"]
    web.client.post("/api/pulse", headers=headers, json={"phase": "speaking", "volume": 0.4})
    assert web.pilots[0].audio.speaking and web.pilots[0].audio.volume == 0.4
    assert web.client.post("/api/stop", headers=headers).status_code == 200
    assert web.pilots[0].last_ride["ended"]
    web.pilots[0].stop.assert_called_once()
    assert (
        web.client.post("/api/action", headers=headers, json={"name": "system_check"}).status_code
        == 409
    )


def test_provider_error_is_sanitized_and_start_can_be_retried(web):
    web.token.side_effect = RuntimeError("sensitive-signed-url")
    response = web.client.post("/api/start", headers=web.headers)
    assert response.status_code == 502 and "sensitive" not in response.text
    assert not web.pilots
    web.token.side_effect = None
    assert web.client.post("/api/start", headers=web.headers).status_code == 200


def test_navigation_controls_work_without_mic_and_share_state_with_voice(web):
    assert web.client.post("/api/navigation", json={"name": "status"}).status_code == 403
    planned = web.client.post(
        "/api/navigation",
        headers=web.headers,
        json={"name": "plan", "parameters": {"destination": "lookout"}},
    )
    assert planned.json()["preview"]["destination_id"] == "lookout"
    web.token.assert_not_called()
    web.client.post(
        "/api/navigation",
        headers=web.headers,
        json={"name": "control", "parameters": {"action": "start"}},
    )
    data = web.client.post("/api/start", headers=web.headers).json()
    headers = {**web.headers, "X-Helmetd-Session": data["session"]}
    result = web.client.post(
        "/api/action", headers=headers, json={"name": "navigation_status"}
    ).json()["result"]
    assert result["route"]["destination_id"] == "lookout" and result["state"] == "navigating"
    web.client.post(
        "/api/action",
        headers=headers,
        json={"name": "navigation_control", "parameters": {"action": "pause"}},
    )
    state = web.client.post("/api/navigation", headers=web.headers, json={"name": "status"})
    assert state.json()["state"] == "paused"
    web.client.post("/api/stop", headers=headers)
    state = web.client.post("/api/navigation", headers=web.headers, json={"name": "status"})
    assert state.json()["state"] == "paused"  # Ending chat does not cancel navigation.
    invalid = web.client.post(
        "/api/navigation",
        headers=web.headers,
        json={"name": "execute_shell", "parameters": {"cmd": "whoami"}},
    )
    assert invalid.status_code == 400


def test_voice_connection_syncs_current_tools_and_stops_if_sync_fails(monkeypatch):
    events = []
    sync = Mock(side_effect=lambda: events.append("sync"))
    monkeypatch.setattr(web_test, "configure_agent", sync)
    monkeypatch.setattr(web_test, "required", lambda _: "agent-test")
    provider = Mock()
    provider.conversational_ai.conversations.get_webrtc_token.side_effect = lambda **kwargs: (
        events.append("token") or SimpleNamespace(token="ephemeral")
    )
    from contextlib import contextmanager

    @contextmanager
    def client():
        yield provider

    monkeypatch.setattr(web_test, "elevenlabs_client", client)
    assert web_test.conversation_token() == "ephemeral"
    assert events == ["sync", "token"]
    sync.side_effect = RuntimeError("offline")
    with pytest.raises(RuntimeError):
        web_test.conversation_token()
    assert events == ["sync", "token"]


def test_voice_hazard_uses_browser_fix_and_appears_on_map_without_publication(tmp_path):
    from helmetd_voice.nearby import NearbyNavigation
    from helmetd_voice.road_hazards import RoadHazards

    now = [1000.0]
    nav = NearbyNavigation(clock=lambda: now[0], wall=lambda: now[0])
    network = Mock()
    hazards = RoadHazards(nav, tmp_path / "reports.sqlite3", wall=lambda: now[0], network=network)
    hazards.refresh = Mock()
    hud = Mock()
    hud.path = tmp_path / "hud.sock"
    hud.request.return_value = {"status": "ok"}

    def pilot_factory(**kwargs):
        pilot = Copilot(hud=hud, directory=tmp_path, **kwargs)
        pilot.start = Mock()
        pilot.stop = Mock()
        return pilot

    app = web_test.create_web_app(lambda: "test-token", pilot_factory, nav, hud, hazards)
    with TestClient(app, base_url="http://127.0.0.1:8016") as client:
        import re

        guard = re.search(r'name="helmetd-token" content="([^"]+)"', client.get("/").text)[1]
        headers = {"Origin": "http://127.0.0.1:8016", "X-Helmetd": guard}
        assert client.post("/api/hazards", json={"name": "report"}).status_code == 403
        client.post(
            "/api/navigation",
            headers=headers,
            json={
                "name": "location",
                "parameters": {"lat": 0, "lon": 0, "accuracy_m": 10, "timestamp_ms": 1000000},
            },
        )
        session = client.post("/api/start", headers=headers).json()["session"]
        voice = {**headers, "X-Helmetd-Session": session}
        result = client.post(
            "/api/action",
            headers=voice,
            json={"name": "report_hazard", "parameters": {"kind": "debris", "lane": "right"}},
        ).json()["result"]
        assert result["status"] == "saved"
        state = client.post("/api/navigation", headers=headers, json={"name": "status"}).json()
        assert state["hazards"]["reports"][0]["lane"] == "right"
        result = client.post("/api/action", headers=voice, json={"name": "nearby_hazards"}).json()[
            "result"
        ]
        assert "point" not in str(result) and result["status"] == "ok"
        network.assert_not_called()
    hazards.close()


def test_camera_controls_work_without_cloud_but_require_origin_guard(web):
    assert web.client.post('/api/hud', json={'action': 'signal', 'value': 'left'}).status_code == 403
    for action, value in [('status', ''), ('signal', 'left'), ('signal', 'off'), ('camera', 'rear')]:
        response = web.client.post('/api/hud', headers=web.headers, json={'action': action, 'value': value})
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
    assert web.client.post('/api/hud', headers=web.headers,
                           json={'action': 'signal', 'value': 'left; reboot'}).status_code == 400
    assert web.client.post('/api/hud', headers=web.headers,
                           json={'action': 'execute', 'value': 'reboot'}).status_code == 422
    web.token.assert_not_called()


def test_map_frame_requires_authorization_and_exact_dimensions(web):
    assert web.client.post("/api/hud/map-frame", content=b"bad").status_code == 403
    assert web.client.post("/api/hud/map-frame", headers=web.headers, content=b"bad").status_code == 400
    frame = bytes([20, 100, 200, 255]) * (640 * 360)
    assert web.client.post("/api/hud/map-frame", headers=web.headers, content=frame).status_code == 200
    assert web.map_path.read_bytes() == frame
    assert web.client.post("/api/hud/map-frame", headers=web.headers, content=frame+b"x").status_code == 413
    assert web.map_path.read_bytes() == frame


def test_game_telemetry_requires_guard_and_rejects_reordered_packets(web):
    packet = dict(session='ride', sequence=1, paused=False, speed_mps=10,
                  gear=2, rpm=4000, signal='left', crashed=False, warnings=['left'])
    assert web.client.post('/api/game/telemetry', json=packet).status_code == 403
    response = web.client.post('/api/game/telemetry', json=packet, headers=web.headers)
    assert response.status_code == 200
    assert response.json()['source'] == 'game'
    assert web.client.post('/api/game/telemetry', json=packet, headers=web.headers).status_code == 409


def test_game_camera_frames_require_active_session_and_exact_size(web):
    url='/api/game/camera/left'
    frame=bytes([10,20,30,255])*(640*360)
    headers={**web.headers,'X-Game-Session':'ride'}
    assert web.client.post(url, content=frame).status_code == 403
    assert web.client.post(url, headers=headers, content=frame).status_code == 409
    packet=dict(session='ride',sequence=1,paused=False,speed_mps=10,
                gear=2,rpm=4000,signal='left',crashed=False,warnings=[])
    assert web.client.post('/api/game/telemetry',headers=web.headers,json=packet).status_code == 200
    assert web.client.post(url,headers=headers,content=frame).status_code == 200
    target=web.map_path.parent/'game-camera-left.bgra'
    assert target.read_bytes() == frame
    assert web.client.post(url,headers=headers,content=frame[:-4]).status_code == 400
    assert web.client.post(url,headers=headers,content=frame+b'x').status_code == 413
    assert web.client.post(url,headers={**headers,'X-Game-Session':'old'},content=frame).status_code == 409
    assert target.read_bytes() == frame
    assert web.client.post('/api/game/camera/unknown',headers=headers,content=frame).status_code == 422


def test_notification_presets_are_guarded_and_validated(web):
    url='/api/hud'
    assert web.client.post(url,json={'action':'notification','value':'messages'}).status_code==403
    for value in ['messages','whatsapp','phone','music']:
        assert web.client.post(url,headers=web.headers,json={'action':'notification','value':value}).status_code==200
    assert web.client.post(url,headers=web.headers,json={'action':'notification','value':'unknown'}).status_code==400
