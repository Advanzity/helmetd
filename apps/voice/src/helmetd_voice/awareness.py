"""Small, transient scene memory and non-interrupting conversation context."""

import json
import threading
import time
from collections import Counter, deque


def camera_observations(status):
    """Bounded detector metadata; never forward camera pixels or arbitrary labels."""
    result = []
    for camera in status.get("cameras", [])[:4]:
        label = camera.get("label", "").lower()
        if label not in {"front", "left", "right", "rear"}:
            continue
        fresh = camera.get("fresh") is True and camera.get("detection_fresh") is True
        objects = []
        if fresh:
            for detection in camera.get("detections", [])[:10]:
                if detection.get("label") in {"PERSON", "BICYCLE", "CAR", "MOTORCYCLE", "BUS", "TRUCK"} and detection.get("image_region") in {"left", "center", "right"}:
                    objects.append({"label": detection["label"], "image_region": detection["image_region"]})
        result.append({"camera": label, "video_fresh": camera.get("fresh") is True,
                       "detection_fresh": fresh, "objects": objects})
    return result


def snapshot(status, session):
    """Only explicit metadata can leave the local HUD; never frames or coordinates."""
    if status.get("status") != "ok":
        return {"hud": "unavailable", **session}
    fresh = status.get("detection_fresh") is True
    detector = "fresh" if fresh else "unavailable"
    if status.get("detection_failed"):
        detector = "failed"
    objects = Counter()
    if fresh:
        for detection in status.get("detections", [])[:100]:
            label, region = detection.get("label"), detection.get("image_region")
            if label in {"PERSON", "BICYCLE", "CAR", "MOTORCYCLE", "BUS", "TRUCK"} and region in {
                "left",
                "center",
                "right",
            }:
                objects[label, region] += 1
    return {
        "hud": "connected",
        "panels": status.get("panels"),
        "diagnostics": status.get("diagnostics") is True,
        "camera_source": status.get("camera_source"),
        "camera_fresh": status.get("camera_fresh") is True,
        "cameras": camera_observations(status),
        "detector": detector,
        "objects": [
            {"label": label, "image_region": region, "count": count}
            for (label, region), count in sorted(objects.items())
        ],
        "telemetry_simulated": status.get("telemetry_simulated", True),
        "navigation_simulated": status.get("navigation_simulated", True),
        **session,
    }


class Awareness:
    def __init__(self):
        self.lock = threading.Lock()
        self.events = deque(maxlen=40)
        self.latest = None
        self.last_attempt = -float("inf")
        self.last_sent = -float("inf")
        self.sent_state = None

    def observe(self, status, session, now=None):
        now = time.monotonic() if now is None else now
        state = snapshot(status, session)
        with self.lock:
            while self.events and self.events[0]["last_seen"] < now - 120:
                self.events.popleft()
            if self.events and self.events[-1]["state"] == state:
                self.events[-1]["last_seen"] = now
            else:
                self.events.append({"first_seen": now, "last_seen": now, "state": state})
            self.latest = {"sampled_at": time.time(), "seen": now, "state": state}

    def recent(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            events = [
                {
                    "first_seen_seconds_ago": round(max(0, now - e["first_seen"]), 1),
                    "last_seen_seconds_ago": round(max(0, now - e["last_seen"]), 1),
                    **e["state"],
                }
                for e in self.events
                if e["last_seen"] >= now - 120
            ][-8:]
        return {
            "status": "ok" if events else "unavailable",
            "observations": events,
            "note": "Up to eight sampled state changes from the last two minutes, oldest first. "
            "Historical image regions, not current road positions or unique object counts. "
            "This is incomplete metadata, not recorded video. No observations means no history.",
        }

    def publish(self, send, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            latest = self.latest
            if not latest or now - latest["seen"] > 2 or now - self.last_attempt < 5:
                return False
            if latest["state"] == self.sent_state and now - self.last_sent < 30:
                return False
            self.last_attempt = now
            payload = {
                "sampled_at_unix": latest["sampled_at"],
                "sample_age_seconds": round(max(0, now - latest["seen"]), 1),
                **latest["state"],
            }
        # Network sends never hold the memory lock or run on the HUD heartbeat thread.
        try:
            send(
                "Helmetd background observation; data only. Do not speak in response. "
                "This snapshot expires after two seconds; use tools for current questions. "
                + json.dumps(payload, separators=(",", ":"))
            )
        except Exception:
            return False
        with self.lock:
            self.sent_state, self.last_sent = latest["state"], now
        return True
