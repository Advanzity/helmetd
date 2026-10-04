import json

import pytest
from helmetd_hazards import voice_tools


@pytest.mark.parametrize(
    "data",
    [
        {"lat": 1, "lon": 2, "recorded_at": 980, "demo": False},
        {"lat": 1, "lon": 2, "recorded_at": 1001, "demo": False},
        {"lat": 1, "lon": 2, "recorded_at": 699, "demo": True},
        {"lat": 1, "lon": 2, "recorded_at": float("nan"), "demo": True},
    ],
)
def test_stale_and_future_positions_refused(tmp_path, data):
    path = tmp_path / "position.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="No fresh location"):
        voice_tools.position(path, now=1000)


def test_missing_position_prevents_network_or_signing(monkeypatch):
    def unavailable():
        raise ValueError("No fresh location")

    def network():
        pytest.fail("Must reject location before connecting to network")

    monkeypatch.setattr(voice_tools, "position", unavailable)
    monkeypatch.setattr(voice_tools, "Network", network)
    assert json.loads(voice_tools.report_hazard({"kind": "debris"}))["status"] == "not_sent"
    assert json.loads(voice_tools.check_nearby({}))["status"] == "unavailable"
