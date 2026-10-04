"""Expiring road observations, connected to real browser location and devnet."""

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

from helmetd_hazards.network import LANES, Network, explorer, nearby, report, wallet

from .maps import distance
from .nearby import projection


class RoadHazards:
    def __init__(
        self,
        navigation,
        path=Path(".local/hazards/reports.sqlite3"),
        wall=time.time,
        network=Network,
        key=wallet,
    ):
        self.navigation, self.wall, self.network, self.key = navigation, wall, network, key
        self.lock = threading.RLock()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Reports contain location: create the database privately before SQLite opens it.
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        path.chmod(0o600)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS reports "
            "(id TEXT PRIMARY KEY, data TEXT NOT NULL, sharing TEXT NOT NULL)"
        )
        self.remote = []
        self.feed_status = "Not synced yet"
        self.synced_at = None

    def _records(self):
        records = [
            json.loads(row[0]) | {"sharing": row[1]}
            for row in self.db.execute("SELECT data, sharing FROM reports")
        ]
        expired = [r["id"] for r in records if r["ts"] + r["ttl"] <= self.wall()]
        self.db.executemany("DELETE FROM reports WHERE id = ?", [(rid,) for rid in expired])
        self.db.commit()
        return [r for r in records if r["id"] not in expired]

    def save(self, parameters):
        lane = parameters.get("lane", "unknown")
        if lane not in LANES:
            raise ValueError("Choose a lane: left, center, right, shoulder or unknown")
        with self.navigation.lock:
            point = self.navigation._origin(guidance=True)
        data = report(parameters.get("kind"), *point, lane=lane, now=self.wall())
        with self.lock:
            for old in self._records():
                if (
                    old["kind"] == data["kind"]
                    and old.get("lane", "unknown") == lane
                    and self.wall() - old["ts"] < 60
                    and distance([old["lat"], old["lon"]], point) < 150
                ):
                    return {
                        "status": "saved",
                        "report_id": old["id"],
                        "duplicate": True,
                        "sharing": old["sharing"],
                        "expires_at": old["ts"] + old["ttl"],
                    }
            self.db.execute(
                "INSERT INTO reports VALUES (?, ?, ?)", (data["id"], json.dumps(data), "local")
            )
            self.db.commit()
        return {
            "status": "saved",
            "report_id": data["id"],
            "kind": data["kind"],
            "lane": lane,
            "sharing": "local",
            "expires_at": data["ts"] + data["ttl"],
            "note": "Saved here for 15 minutes. Not shared with other riders yet.",
        }

    def share(self, parameters):
        if parameters.get("confirmed") is not True:
            raise ValueError("Confirm public approximate location sharing on Solana devnet first")
        with self.lock:
            data = next(
                (r for r in self._records() if r["id"] == parameters.get("report_id")), None
            )
            if not data:
                raise ValueError("That report is missing or expired")
            if data["sharing"] != "local":
                return {
                    "status": data["sharing"],
                    "report_id": data["id"],
                    "note": "Already attempted. Do not submit a replacement.",
                }
            # A durable attempt marker blocks duplicate sends, including after a restart.
            self.db.execute(
                "UPDATE reports SET sharing = ? WHERE id = ?", ("unconfirmed", data["id"])
            )
            self.db.commit()
            data.pop("sharing")
            data["published_at"] = int(self.wall())
        try:
            with self.network() as network:
                signature = network.publish(self.key(), data)
        except ValueError as error:
            # Network's validation/fee checks fail before submission. Unlike an
            # uncertain send, these are safe for the rider to retry after fixing setup.
            with self.lock:
                self.db.execute(
                    "UPDATE reports SET sharing = ? WHERE id = ?", ("local", data["id"])
                )
                self.db.commit()
            return {"status": "not_sent", "report_id": data["id"], "reason": str(error)}
        except Exception:
            return {
                "status": "unconfirmed",
                "report_id": data["id"],
                "reason": "Sharing could not be confirmed. Report remains saved locally. "
                "Check the transaction outbox before retrying.",
            }
        with self.lock:
            self.db.execute(
                "UPDATE reports SET sharing = ? WHERE id = ?", ("confirmed", data["id"])
            )
            self.db.commit()
        return {"status": "confirmed", "report_id": data["id"], "transaction": explorer(signature)}

    def refresh(self):
        try:
            riders = [
                r.strip() for r in os.getenv("HELMETD_TRUSTED_RIDERS", "").split(",") if r.strip()
            ] or [str(self.key().pubkey())]
            with self.network() as network:
                events = network.events(riders)
            with self.lock:
                self.remote = events
                self.synced_at = self.wall()
                self.feed_status = "Trusted-rider feed synced"
        except Exception:
            with self.lock:
                self.feed_status = "Feed offline · saved reports still available"

    def snapshot(self, nav=None, private=False):
        nav = nav or self.navigation.snapshot()
        fix = nav.get("fix")
        with self.lock:
            own = self._records()
            status, synced_at = self.feed_status, self.synced_at
            if not fix or not fix.get("guidance_usable"):
                return {
                    "reports": [],
                    "status": status,
                    "synced_at": synced_at,
                    "location_required": True,
                }
            # Signed network events are validated by Network before entering this cache.
            remote = nearby(self.remote, *fix["point"], radius=3000, now=self.wall())
            records = {r["id"]: r | {"sharing": "community"} for r in remote}
            records.update({r["id"]: r for r in own})
        results = []
        for r in records.values():
            point = [r["lat"], r["lon"]]
            away = distance(fix["point"], point)
            if away > 3000:
                continue
            ahead = None
            route = nav.get("route")
            if route and nav["state"] == "navigating" and nav.get("next_turn"):
                candidates = []
                for i, (a, b) in enumerate(zip(route["geometry"], route["geometry"][1:])):
                    cross, ratio = projection(point, a, b)
                    along = route["cumulative"][i] + ratio * (
                        route["cumulative"][i + 1] - route["cumulative"][i]
                    )
                    candidates.append((cross, along - nav["progress_m"]))
                cross, along = min(candidates, default=(float("inf"), -1))
                # Rounded coordinates cannot establish a lane or carriageway. Describe
                # the match as near the upcoming route, never as a confirmed obstruction.
                if cross <= 100 and 50 <= along <= 700:
                    ahead = round(along)
            item = {
                "id": r["id"],
                "kind": r["kind"],
                "lane": r.get("lane", "unknown"),
                "reported_at": r["ts"],
                "expires_at": r["ts"] + r["ttl"],
                "distance_m": round(away),
                "ahead_m": ahead,
                "sharing": r["sharing"],
                "point": point,
            }
            if private:
                item.pop("point")
            results.append(item)
        return {
            "reports": sorted(results, key=lambda r: r["distance_m"])[:32],
            "status": status,
            "synced_at": synced_at,
            "location_required": False,
            "note": "Rider observations, not verified conditions. Lane is rider-reported.",
        }

    def close(self):
        self.db.close()
