"""A small trusted-rider feed using signed Solana memos; devnet only."""

import base64
import json
import math
import os
import time
import uuid
from pathlib import Path

import httpx
from solders.hash import Hash
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.message import MessageV0, to_bytes_versioned
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

RPC_URL = "https://api.devnet.solana.com"
DEVNET_GENESIS = "EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG"
MEMO = Pubkey.from_string("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr")
KINDS = ("debris", "pothole", "blocked_lane", "standing_water")
LANES = ("unknown", "left", "center", "right", "shoulder")
WALLET = Path(".local/hazards/devnet-wallet.json")


def wallet(path=WALLET, create=False):
    if not path.exists() and create:
        path.parent.mkdir(parents=True, exist_ok=True)
        key = Keypair()
        with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as f:
            json.dump(list(bytes(key)), f)
    if path.stat().st_mode & 0o077:
        raise ValueError("Wallet file must have private permissions (chmod 600)")
    return Keypair.from_bytes(bytes(json.loads(path.read_text())))


def coordinates(lat, lon):
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90:
        raise ValueError("Invalid coordinates")
    if not -180 <= lon <= 180:
        raise ValueError("Invalid coordinates")
    return round(lat, 3), round(lon, 3)


def report(kind, lat, lon, ttl=900, demo=False, now=None, lane="unknown"):
    lat, lon = coordinates(lat, lon)
    data = {
        "app": "helmetd-hazards",
        "v": 2,
        "op": "report",
        "id": uuid.uuid4().hex,
        "kind": kind,
        "lane": lane,
        "lat": lat,
        "lon": lon,
        "ttl": ttl,
        "ts": int(time.time() if now is None else now),
        "demo": demo,
    }
    data["published_at"] = data["ts"]
    validate(data)
    return data


def clear(report_id, now=None):
    data = {
        "app": "helmetd-hazards",
        "v": 1,
        "op": "clear",
        "id": report_id,
        "ts": int(time.time() if now is None else now),
    }
    validate(data)
    return data


def validate(data):
    if (
        not isinstance(data, dict)
        or data.get("app") != "helmetd-hazards"
        or data.get("v") not in (1, 2)
    ):
        raise ValueError("Unknown hazard protocol")
    if not isinstance(data.get("id"), str) or len(data["id"]) != 32:
        raise ValueError("Invalid report ID")
    int(data["id"], 16)
    if type(data.get("ts")) is not int or data["ts"] < 0:
        raise ValueError("Invalid report time")
    common = {"app", "v", "op", "id", "ts"}
    if data.get("op") == "clear":
        if set(data) != common:
            raise ValueError("Unexpected clear fields")
        return
    fields = common | {"kind", "lat", "lon", "ttl", "demo"}
    if data["v"] == 2:
        fields.update({"lane", "published_at"})
        if data.get("lane") not in LANES:
            raise ValueError("Unsupported lane")
        if (
            type(data.get("published_at")) is not int
            or not data["ts"] <= data["published_at"] <= data["ts"] + 3600
        ):
            raise ValueError("Invalid publication time")
    if data.get("op") != "report" or set(data) != fields:
        raise ValueError("Unexpected report fields")
    if data["kind"] not in KINDS or type(data["demo"]) is not bool:
        raise ValueError("Unsupported road hazard")
    if type(data["ttl"]) is not int or not 60 <= data["ttl"] <= 3600:
        raise ValueError("Reports must expire in 60..3600 seconds")
    if type(data["lat"]) not in (int, float) or type(data["lon"]) not in (int, float):
        raise ValueError("Invalid coordinates")
    if coordinates(data["lat"], data["lon"]) != (data["lat"], data["lon"]):
        raise ValueError("Report locations must be rounded to three decimal places")


def signed_transaction(key, data, blockhash):
    validate(data)
    payload = json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
    if len(payload) > 500:
        raise ValueError("Report exceeds memo size budget")
    instruction = Instruction(MEMO, payload, [AccountMeta(key.pubkey(), True, False)])
    message = MessageV0.try_compile(key.pubkey(), [instruction], [], Hash.from_string(blockhash))
    return VersionedTransaction(message, [key])


def decode_event(result, signature, author, now):
    """Validate the actual transaction, not the untrusted memo summary in the index."""
    try:
        if not result or not result.get("meta") or result["meta"].get("err") is not None:
            return None
        block_time = result["blockTime"]
        if type(block_time) is not int or not now - 3720 <= block_time <= now + 30:
            return None
        encoded, encoding = result["transaction"]
        if encoding != "base64" or len(encoded) > 2000:
            return None
        tx = VersionedTransaction.from_bytes(base64.b64decode(encoded, validate=True))
        tx.verify_and_hash_message()
        if str(tx.signatures[0]) != signature:
            return None
        msg = tx.message
        if msg.header.num_required_signatures != 1 or str(msg.account_keys[0]) != author:
            return None
        if len(msg.instructions) != 1:
            return None
        ix = msg.instructions[0]
        if msg.account_keys[ix.program_id_index] != MEMO or list(ix.accounts) != [0]:
            return None
        data = json.loads(bytes(ix.data))
        validate(data)
        if abs(data.get("published_at", data["ts"]) - block_time) > 120 or data["ts"] > now + 30:
            return None
        return {**data, "author": author, "signature": signature, "block_time": block_time}
    except (ValueError, TypeError, KeyError, IndexError):
        return None
    except Exception:
        # Rust SDK signature/sanitization exceptions must not break the whole feed.
        return None


def distance_m(lat, lon, other_lat, other_lon):
    a, b = math.radians(lat), math.radians(other_lat)
    h = math.sin((b - a) / 2) ** 2 + math.cos(a) * math.cos(b) * (
        math.sin(math.radians(other_lon - lon) / 2) ** 2
    )
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def nearby(events, lat, lon, radius=1000, include_demo=False, now=None):
    coordinates(lat, lon)
    if not math.isfinite(radius) or not 50 <= radius <= 10000:
        raise ValueError("Radius must be 50..10000 metres")
    now = time.time() if now is None else now
    reports = {}
    clears = []
    for event in events:
        if event["op"] == "clear":
            clears.append(event)
        elif event["ts"] <= now and event["ts"] + event["ttl"] > now:
            reports[(event["author"], event["id"])] = event
    results = []
    for (author, report_id), event in reports.items():
        if event["demo"] and not include_demo:
            continue
        observers = {
            c["author"] for c in clears if c["id"] == report_id and event["ts"] <= c["ts"] <= now
        }
        # Reporter's retraction or two independent trusted observers clears a report.
        if author in observers or len(observers - {author}) >= 2:
            continue
        distance = distance_m(lat, lon, event["lat"], event["lon"])
        if distance <= radius:
            results.append(
                {
                    **event,
                    "distance_m": round(distance),
                    "clear_observations": len(observers),
                    "expires_at": event["ts"] + event["ttl"],
                }
            )
    return sorted(results, key=lambda x: x["distance_m"])


class Network:
    def __init__(self, url=RPC_URL):
        if not url.startswith("https://"):
            raise ValueError("Use an HTTPS Solana devnet RPC")
        self.http = httpx.Client(base_url=url, timeout=15)
        self.deadline = time.monotonic() + 40
        try:
            if self.rpc("getGenesisHash") != DEVNET_GENESIS:
                raise ValueError("Only Solana devnet is supported; refusing this network")
        except BaseException:
            self.http.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.http.close()

    def rpc(self, method, params=None):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Solana operation timed out")
        response = self.http.post(
            "",
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []},
            timeout=min(15, remaining),
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"Solana {method} failed (code {data['error'].get('code')})")
        return data["result"]

    def balance(self, address):
        return self.rpc("getBalance", [address, {"commitment": "confirmed"}])["value"]

    def publish(self, key, data, outbox=Path(".local/hazards/outbox")):
        block = self.rpc("getLatestBlockhash", [{"commitment": "confirmed"}])["value"]
        tx = signed_transaction(key, data, block["blockhash"])
        message = base64.b64encode(to_bytes_versioned(tx.message)).decode()
        fee = self.rpc("getFeeForMessage", [message, {"commitment": "confirmed"}])["value"]
        if fee is None or fee > 10000:
            raise ValueError("Unexpected transaction fee; report was not sent")
        if self.balance(str(key.pubkey())) < fee:
            raise ValueError("Devnet wallet needs test SOL; run helmetd-hazards airdrop")
        signature = str(tx.signatures[0])
        packet = base64.b64encode(bytes(tx)).decode()
        outbox.mkdir(parents=True, exist_ok=True)
        path = outbox / f"{signature}.json"
        path.write_text(
            json.dumps(
                {
                    "signature": signature,
                    "data": data,
                    "packet": packet,
                    "last_valid_block_height": block["lastValidBlockHeight"],
                }
            )
        )
        print(f"Transaction: {explorer(signature)}", flush=True)
        try:
            result = self.rpc(
                "sendTransaction",
                [
                    packet,
                    {
                        "encoding": "base64",
                        "skipPreflight": False,
                        "preflightCommitment": "confirmed",
                        "maxRetries": 2,
                    },
                ],
            )
            if result != signature:
                raise RuntimeError("Unexpected transaction signature")
            if not self.confirm(signature):
                raise RuntimeError("Confirmation pending")
        except Exception:
            raise RuntimeError(
                f"Transaction unconfirmed; check {explorer(signature)}. "
                "Do not submit a replacement until its status is known."
            ) from None
        return signature

    def confirm(self, signature):
        for _ in range(15):
            status = self.rpc(
                "getSignatureStatuses", [[signature], {"searchTransactionHistory": True}]
            )["value"][0]
            if status:
                if status["err"] is not None:
                    raise RuntimeError("Transaction failed on-chain")
                if status["confirmationStatus"] in ("confirmed", "finalized"):
                    return True
            time.sleep(1)
        return False

    def events(self, riders, now=None):
        now = time.time() if now is None else now
        if not 1 <= len(riders) <= 8:
            raise ValueError("Configure 1..8 trusted rider public keys")
        events = []
        for rider in set(riders):
            Pubkey.from_string(rider)
            signatures = self.rpc(
                "getSignaturesForAddress", [rider, {"limit": 100, "commitment": "confirmed"}]
            )
            for item in signatures:
                if item.get("blockTime") and item["blockTime"] < now - 3720:
                    break
                if item["err"] or "helmetd-hazards" not in (item.get("memo") or ""):
                    continue
                signature = item["signature"]
                result = self.rpc(
                    "getTransaction",
                    [
                        signature,
                        {
                            "encoding": "base64",
                            "maxSupportedTransactionVersion": 0,
                            "commitment": "confirmed",
                        },
                    ],
                )
                event = decode_event(result, signature, rider, now)
                if event:
                    events.append(event)
        return events


def explorer(signature):
    return f"https://explorer.solana.com/tx/{signature}?cluster=devnet"
