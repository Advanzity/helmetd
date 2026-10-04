import base64
import copy

import httpx
import pytest
from helmetd_hazards.network import (
    Network,
    clear,
    decode_event,
    nearby,
    report,
    signed_transaction,
    wallet,
)
from solders.hash import Hash
from solders.keypair import Keypair


def verified(data, key=None):
    key = key or Keypair()
    tx = signed_transaction(key, data, str(Hash.default()))
    result = {
        "meta": {"err": None},
        "blockTime": 1000,
        "transaction": [base64.b64encode(bytes(tx)).decode(), "base64"],
    }
    return decode_event(result, str(tx.signatures[0]), str(key.pubkey()), 1001), result, tx


def test_signed_report_can_be_read_by_another_rider():
    data = report("debris", 42.12345, -83.12345, now=1000)
    event, _, _ = verified(data)
    assert (event["lat"], event["lon"]) == (42.123, -83.123)
    found = nearby([event], 42.123, -83.122, now=1001)
    assert len(found) == 1
    assert 70 < found[0]["distance_m"] < 100


def test_delayed_sharing_preserves_observation_expiry_and_signed_lane():
    data = report("debris", 1, 1, now=700, lane="right")
    data["published_at"] = 1000
    event, _, _ = verified(data)
    assert event["lane"] == "right" and event["ts"] == 700
    assert nearby([event], 1, 1, now=1001)[0]["expires_at"] == 1600
    assert not nearby([event], 1, 1, now=1600)


def test_invalid_signature_wrong_author_failed_or_unconfirmed_rejected():
    key = Keypair()
    event, result, tx = verified(report("pothole", 1, 1, now=1000), key)
    assert event
    signature, author = str(tx.signatures[0]), str(key.pubkey())
    assert decode_event(None, signature, author, 1001) is None
    assert decode_event(result, signature, str(Keypair().pubkey()), 1001) is None
    corrupt = bytearray(bytes(tx))
    corrupt[10] ^= 1
    bad = copy.deepcopy(result)
    bad["transaction"][0] = base64.b64encode(corrupt).decode()
    assert decode_event(bad, signature, author, 1001) is None
    bad = copy.deepcopy(result)
    bad["meta"]["err"] = "failed"
    assert decode_event(bad, signature, author, 1001) is None
    assert decode_event(result, signature, author, 5000) is None


def test_expired_distant_and_demo_reports_filtered():
    event, _, _ = verified(report("debris", 1, 1, ttl=60, now=1000))
    assert not nearby([event], 1, 1, now=1060)
    assert not nearby([event], 2, 2, now=1001)
    event["demo"] = True
    assert not nearby([event], 1, 1, now=1001)
    assert nearby([event], 1, 1, include_demo=True, now=1001)


def test_clear_requires_reporter_or_two_distinct_observers():
    key = Keypair()
    event, _, _ = verified(report("debris", 1, 1, now=1000), key)
    c1, _, _ = verified(clear(event["id"], now=1000))
    c2, _, _ = verified(clear(event["id"], now=1000))
    assert nearby([event, c1, c1], 1, 1, now=1001)
    assert not nearby([event, c1, c2], 1, 1, now=1001)
    own, _, _ = verified(clear(event["id"], now=1000), key)
    assert not nearby([event, own], 1, 1, now=1001)


@pytest.mark.parametrize(
    "lat,lon,ttl", [(float("nan"), 0, 60), (91, 0, 60), (0, 181, 60), (0, 0, 3601), (0, 0, 0)]
)
def test_invalid_reports_rejected_before_signing(lat, lon, ttl):
    with pytest.raises(ValueError):
        report("debris", lat, lon, ttl)


def test_wallet_is_private_and_reused(tmp_path):
    path = tmp_path / "wallet.json"
    one = wallet(path, create=True)
    assert path.stat().st_mode & 0o777 == 0o600
    assert wallet(path, create=True).pubkey() == one.pubkey()


def test_refuses_other_network_before_any_transaction(monkeypatch):
    original = httpx.Client
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"result": "mainnet-genesis"})

    monkeypatch.setattr(
        httpx, "Client", lambda **kw: original(**kw, transport=httpx.MockTransport(respond))
    )
    with pytest.raises(ValueError, match="Only Solana devnet"):
        Network()
    assert len(requests) == 1
