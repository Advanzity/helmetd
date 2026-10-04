import json
from unittest.mock import Mock

import pytest
from helmetd_hazards.network import report
from helmetd_voice.nearby import NearbyNavigation
from helmetd_voice.road_hazards import RoadHazards


@pytest.fixture
def hazards(tmp_path):
    now = [1000.0]
    nav = NearbyNavigation(clock=lambda: now[0], wall=lambda: now[0])
    network = Mock()
    network.return_value.__enter__ = Mock(return_value=network)
    network.return_value.__exit__ = Mock(return_value=False)
    service = RoadHazards(
        nav, tmp_path / "reports.sqlite3", wall=lambda: now[0], network=network, key=Mock()
    )

    def fix(lat=0, accuracy=10):
        now[0] += 1
        nav.location({"lat": lat, "lon": 0, "accuracy_m": accuracy, "timestamp_ms": now[0] * 1000})

    yield service, nav, now, network, fix
    service.close()


def test_report_requires_fresh_accurate_location_and_valid_lane(hazards):
    service, _, now, network, fix = hazards
    with pytest.raises(ValueError, match="location"):
        service.save({"kind": "debris", "lane": "right"})
    fix(accuracy=100)
    with pytest.raises(ValueError, match="imprecise"):
        service.save({"kind": "debris"})
    fix()
    with pytest.raises(ValueError, match="lane"):
        service.save({"kind": "debris", "lane": "invented"})
    now[0] += 16
    with pytest.raises(ValueError, match="location"):
        service.save({"kind": "debris"})
    network.assert_not_called()


def test_save_deduplicates_persists_and_expires_without_publication(hazards, tmp_path):
    service, _, now, network, fix = hazards
    fix()
    first = service.save({"kind": "debris", "lane": "right"})
    again = service.save({"kind": "debris", "lane": "right"})
    assert first["report_id"] == again["report_id"] and again["duplicate"]
    assert first["expires_at"] == 1901
    assert (tmp_path / "reports.sqlite3").stat().st_mode & 0o777 == 0o600
    view = service.snapshot(private=True)
    assert view["reports"][0]["lane"] == "right"
    assert "point" not in json.dumps(view) and "lat" not in view["reports"][0]
    network.assert_not_called()
    now[0] = 1901
    fix()
    assert service.snapshot()["reports"] == []
    assert service.db.execute("SELECT count(*) FROM reports").fetchone()[0] == 0


def test_share_requires_confirmation_and_never_retries_uncertain_send(hazards):
    service, _, _, network, fix = hazards
    fix()
    saved = service.save({"kind": "pothole"})
    with pytest.raises(ValueError, match="Confirm"):
        service.share({"report_id": saved["report_id"], "confirmed": False})
    network.assert_not_called()
    network.publish.side_effect = RuntimeError("timeout")
    params = {"report_id": saved["report_id"], "confirmed": True}
    assert service.share(params)["status"] == "unconfirmed"
    assert service.share(params)["status"] == "unconfirmed"
    network.publish.assert_called_once()
    assert service.snapshot()["reports"][0]["sharing"] == "unconfirmed"


def test_confirmed_publication_preserves_lane_time_and_original_location(hazards):
    service, _, _, network, fix = hazards
    fix(lat=0.002)
    saved = service.save({"kind": "debris", "lane": "right"})
    fix(lat=0.005)
    network.publish.return_value = "test-signature"
    result = service.share({"report_id": saved["report_id"], "confirmed": True})
    assert result["status"] == "confirmed"
    packet = network.publish.call_args.args[1]
    assert packet["lane"] == "right" and packet["lat"] == 0.002 and packet["ts"] == 1001


def test_known_preflight_failure_is_not_an_uncertain_submission(hazards):
    service, _, _, network, fix = hazards
    fix()
    saved = service.save({"kind": "debris"})
    network.publish.side_effect = ValueError("Devnet wallet needs test SOL")
    result = service.share({"report_id": saved["report_id"], "confirmed": True})
    assert result["status"] == "not_sent"
    assert service.snapshot()["reports"][0]["sharing"] == "local"


def test_approaching_route_matching_excludes_behind_cross_street_and_expired(hazards):
    service, _, now, _, fix = hazards
    fix()

    def event(lat, lon=0, **kw):
        return report("debris", lat, lon, now=1000, **kw) | {"author": "trusted"}

    ahead, behind, off, expired = (
        event(0.005),
        event(-0.003),
        event(0.005, 0.003),
        event(0.002, ttl=60),
    )
    service.remote = [ahead, behind, off, expired]
    now[0] = 1070
    data = {
        "fix": {"point": [0, 0], "guidance_usable": True},
        "state": "navigating",
        "next_turn": {"id": 1},
        "progress_m": 0,
        "route": {"geometry": [[0, 0], [0.01, 0]], "cumulative": [0, 1112]},
    }
    found = {r["id"]: r for r in service.snapshot(data)["reports"]}
    assert 500 < found[ahead["id"]]["ahead_m"] < 600
    assert found[behind["id"]]["ahead_m"] is None
    assert found[off["id"]]["ahead_m"] is None
    assert expired["id"] not in found
    data["state"] = "paused"
    assert all(r["ahead_m"] is None for r in service.snapshot(data)["reports"])
    data["fix"]["guidance_usable"] = False
    assert service.snapshot(data)["reports"] == []


def test_legacy_signed_reports_still_work_and_new_lane_is_signed():
    from helmetd_hazards.network import validate

    legacy = report("debris", 1, 1, now=1000)
    legacy["v"] = 1
    legacy.pop("lane")
    legacy.pop("published_at")
    validate(legacy)
    with pytest.raises(ValueError, match="lane"):
        report("debris", 1, 1, lane="not-a-lane")
