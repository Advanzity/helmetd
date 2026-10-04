"""Real nearby routes and explicit, freshness-gated browser location input."""

import copy
import math
import threading
import time

from .maps import Maps, coordinate, distance
from .hud_map import map_command


def projection(point, a, b):
    scale = math.cos(math.radians(point[0]))
    vector = [(b[1] - a[1]) * scale, b[0] - a[0]]
    offset = [(point[1] - a[1]) * scale, point[0] - a[0]]
    squared = sum(value * value for value in vector)
    ratio = max(0, min(1, sum(v * o for v, o in zip(vector, offset)) / squared)) if squared else 0
    projected = [a[i] + (b[i] - a[i]) * ratio for i in (0, 1)]
    return distance(point, projected), ratio


class NearbyNavigation:
    def __init__(self, maps=None, clock=time.monotonic, wall=time.time):
        self.maps = maps or Maps()
        self.clock, self.wall = clock, wall
        self.lock = threading.RLock()
        self.fix = None
        self.route = self.preview = None
        self.results = []
        self.known_places = {}
        self.state = "idle"
        self.revision = self.operation = 0
        self.progress = 0.0
        self.off_count = self.arrival_count = 0
        self.last_progress_stamp = None
        self.stop_visited = False
        self.route_generation = 0
        self.route_reason = "started"
        self.repeat_serial = 0
        self.notice = "Use your location to find places nearby."

    def touch(self):
        pass

    def _origin(self, guidance=False):
        if not self.fix or self.clock() - self.fix["received"] > (15 if guidance else 300):
            raise ValueError("Refresh your location before continuing")
        if self.fix["accuracy_m"] > (60 if guidance else 3000):
            raise ValueError(
                "Location is too imprecise. Move near a window or use a phone with GPS."
            )
        return self.fix["point"][:]

    def location(self, p):
        point = coordinate(p.get("lat"), p.get("lon"))
        accuracy, stamp = p.get("accuracy_m"), p.get("timestamp_ms")
        if (
            type(accuracy) not in (int, float)
            or not math.isfinite(accuracy)
            or not 0 < accuracy <= 100000
            or type(stamp) not in (int, float)
            or not math.isfinite(stamp)
            or not -3 <= self.wall() - stamp / 1000 <= 20
        ):
            raise ValueError("A fresh browser location with valid accuracy is required")
        with self.lock:
            if self.fix and stamp <= self.fix["timestamp_ms"]:
                return self.summary()
            self.fix = {
                "point": point,
                "accuracy_m": accuracy,
                "timestamp_ms": stamp,
                "received": self.clock() - max(0, self.wall() - stamp / 1000),
            }
            if self.state == "location_lost":
                if accuracy <= 60 and self.clock() - self.fix["received"] <= 15:
                    self.state = "paused" if self.route else "idle"
                    self.notice = "Location received. Resume guidance when ready."
            elif not self.route and not self.preview:
                self.notice = "Location received. Find a nearby stop or search for a destination."
            if self.state == "navigating":
                self._update_progress()
            self.revision += 1
            return self.summary()

    def clear_location(self):
        with self.lock:
            self.fix = None
            self.operation += 1
            self.preview = None
            self.state = "location_lost" if self.route else "idle"
            self.notice = "Location sharing stopped. Guidance is suspended."
            self.revision += 1
            return self.summary()

    def search(self, p):
        query = p.get("query")
        if not isinstance(query, str):
            raise ValueError("Enter a place name or nearby category")
        with self.lock:
            origin = self._origin()
            self.operation += 1
            operation = self.operation
        found = self.maps.search(query, origin)
        with self.lock:
            if operation != self.operation or not self.fix:
                raise ValueError("Search was superseded. Try the latest request again.")
            self.results = found
            for place in found:
                self.known_places[place["id"]] = (self.clock(), place)
            self.known_places = {
                key: value
                for key, value in self.known_places.items()
                if self.clock() - value[0] < 900
            }
            while len(self.known_places) > 64:
                self.known_places.pop(next(iter(self.known_places)))
            self.notice = (
                f"Found {len(found)} nearby places."
                if found
                else "No matching nearby places found. Try another search."
            )
            self.revision += 1
            return {
                "status": "ok",
                "results": [self._place_summary(place) for place in found],
                "note": (
                    "Distances are straight-line estimates, not riding distances. "
                    "Opening hours are not verified."
                ),
            }

    @staticmethod
    def _place_summary(place):
        return {key: value for key, value in place.items() if key != "point"}

    def _resolve(self, value):
        if not isinstance(value, str):
            raise ValueError("Choose a place from the nearby results")
        selected = self.known_places.get(value)
        for route in (self.preview, self.route):
            if route and value == route["destination_id"]:
                return copy.deepcopy(route["destination_place"])
        if selected and self.clock() - selected[0] < 900:
            return copy.deepcopy(selected[1])
        matches = [
            place
            for at, place in self.known_places.values()
            if self.clock() - at < 900 and place["name"].lower() == value.strip().lower()
        ]
        if len(matches) == 1:
            return copy.deepcopy(matches[0])
        raise ValueError("Search for that destination first, then choose one specific result")

    def _plan(self, destination, preference, stop=None):
        with self.lock:
            origin = self._origin()
            self.operation += 1
            operation = self.operation
        planned = self.maps.route(origin, destination, preference, stop)
        with self.lock:
            if operation != self.operation or not self.fix:
                raise ValueError("Route request was superseded. Preview again.")
            if distance(origin, self.fix["point"]) > 100:
                raise ValueError("Your position changed while routing. Preview again from here.")
            self.preview = planned
            self.notice = "Route preview ready. Start when you are ready."
            self.revision += 1
            return self.summary()

    def plan(self, p):
        with self.lock:
            destination = self._resolve(p.get("destination"))
        return self._plan(destination, p.get("preference", "fastest"))

    def stop(self, p):
        with self.lock:
            selected = self.preview or self.route
            if not selected:
                raise ValueError("Choose a destination before editing stops")
            if p.get("action") not in ("add", "remove"):
                raise ValueError("Choose add or remove")
            stop = self._resolve(p.get("place")) if p["action"] == "add" else None
            if stop and stop["id"] == selected["destination_id"]:
                raise ValueError("That place is already your destination")
            destination, preference = selected["destination_place"], selected["preference"]
        return self._plan(destination, preference, stop)

    def control(self, p):
        action = p.get("action")
        if action == "reroute":
            with self.lock:
                if not self.route:
                    raise ValueError("Start a route before rerouting")
                destination, preference = self.route["destination_place"], self.route["preference"]
                stop = None if self.stop_visited else self.route["stop_place"]
            self._plan(destination, preference, stop)
            with self.lock:
                self.control({"action": "start"})
                self.route_reason = "rerouted"
                return self.summary()
        with self.lock:
            if action == "cancel_preview":
                self.operation += 1
                self.preview = None
                self.notice = "Preview dismissed."
            elif action == "cancel":
                self.operation += 1
                self.route = self.preview = None
                self.state = "idle"
                self.notice = "Navigation cancelled. Location sharing remains on until you stop it."
            elif action == "start":
                origin = self._origin(guidance=True)
                if not self.preview:
                    if self.state == "navigating":
                        return self.summary()
                    raise ValueError("Choose and preview a route first")
                if distance(origin, self.preview["origin"]) > 100:
                    raise ValueError("Your starting position changed. Preview this route again.")
                self.route, self.preview = self.preview, None
                self.route_generation += 1
                self.route_reason = "started"
                self.progress = 0
                self.off_count = self.arrival_count = 0
                self.last_progress_stamp = None
                self.stop_visited = False
                self.state = "navigating"
                self.notice = "Guidance started. Progress follows your device location."
                self._update_progress()
            elif action == "pause":
                if not self.route or self.state not in ("navigating", "paused"):
                    raise ValueError("No active route to pause")
                self.state = "paused"
                self.notice = "Guidance paused."
            elif action == "resume":
                self._origin(guidance=True)
                if not self.route or self.state not in ("paused", "navigating"):
                    raise ValueError("No paused route to resume; reroute if you are off route")
                self.state = "navigating"
                self.notice = "Guidance resumed."
                self._update_progress()
            elif action == "repeat":
                self.repeat_serial += 1
                return self.summary()
            else:
                raise ValueError("Unknown navigation action")
            self.revision += 1
            return self.summary()

    def _update_progress(self):
        try:
            point = self._origin(guidance=True)
        except ValueError:
            self.state = "location_lost"
            self.notice = "Location is stale or too imprecise. Guidance is suspended."
            return
        if self.last_progress_stamp == self.fix["timestamp_ms"]:
            return
        self.last_progress_stamp = self.fix["timestamp_ms"]
        route = self.route
        candidates = []
        for index, (a, b) in enumerate(zip(route["geometry"], route["geometry"][1:])):
            away, ratio = projection(point, a, b)
            along = route["cumulative"][index] + ratio * (
                route["cumulative"][index + 1] - route["cumulative"][index]
            )
            # Prefer local progress around loops and intersections; never skip kilometres.
            if self.progress - 100 <= along <= self.progress + 400:
                candidates.append((away, abs(along - self.progress), along))
        best = min(candidates, default=(math.inf, 0, self.progress))
        if best[0] > max(40, self.fix["accuracy_m"] * 1.5):
            self.off_count += 1
            self.arrival_count = 0
            self.notice = "Checking your position against the route. Turn guidance is suspended."
            if self.off_count >= 2:
                self.state = "off_route"
                self.notice = "You appear off route. Reroute from your current position."
            return
        if self.off_count:
            self.notice = "Back on route. Guidance resumed."
        self.off_count = 0
        self.progress = max(self.progress, best[2])
        # Arrival needs two distinct accurate fixes, route-end progress AND proximity.
        near_end = (
            route["cumulative"][-1] - self.progress < 35
            and distance(point, route["geometry"][-1]) < 35
        )
        self.arrival_count = (
            self.arrival_count + 1 if near_end and self.fix["accuracy_m"] <= 25 else 0
        )
        if self.arrival_count >= 2:
            self.state = "arrived"
            self.notice = f"Arrived near {route['destination']}."
            return
        if route["stop_place"] and not self.stop_visited:
            stop = next((m for m in route["maneuvers"] if m["stop"]), None)
            if (
                stop
                and abs(route["cumulative"][stop["begin"]] - self.progress) < 30
                and self.fix["accuracy_m"] <= 25
            ):
                self.stop_visited = True
                self.state = "paused"
                self.notice = f"Stop reached: {route['stop_place']['name']}. Resume when ready."

    def tick(self):
        with self.lock:
            if self.state == "navigating":
                try:
                    self._origin(guidance=True)
                except ValueError:
                    self.state = "location_lost"
                    self.notice = "Location updates stopped. Guidance is suspended."
                    self.revision += 1

    def snapshot(self):
        with self.lock:
            self.tick()
            next_turn, remaining, seconds = None, None, None
            if self.route and self.state in ("navigating", "arrived") and not self.off_count:
                route = self.route
                remaining = max(0, route["cumulative"][-1] - self.progress)
                seconds = route["duration_s"] * remaining / route["cumulative"][-1]
                upcoming = [
                    m
                    for m in route["maneuvers"]
                    if route["cumulative"][m["begin"]] > self.progress + 8
                ]
                maneuver = upcoming[0] if upcoming else route["maneuvers"][-1]
                kind = maneuver["type"]
                icon = (
                    "left"
                    if kind in (14, 15, 16, 22, 25, 28)
                    else "right"
                    if kind in (9, 10, 11, 21, 24, 27)
                    else "uturn"
                    if kind in (12, 13)
                    else "arrive"
                    if kind in (4, 5, 6)
                    else "straight"
                )
                next_turn = {
                    "id": route["maneuvers"].index(maneuver),
                    "instruction": maneuver["instruction"],
                    "street": maneuver.get("street", ""),
                    "maneuver": icon,
                    "distance_m": round(
                        max(0, route["cumulative"][maneuver["begin"]] - self.progress)
                    ),
                }
                if self.state == "arrived":
                    remaining = seconds = 0
                    next_turn = None
            fix = None
            if self.fix:
                fix = {key: value for key, value in self.fix.items() if key != "received"}
                fix["age_s"] = round(max(0, self.clock() - self.fix["received"]), 1)
                fix["guidance_usable"] = fix["age_s"] <= 15 and fix["accuracy_m"] <= 60
            return copy.deepcopy(
                {
                    "status": "ok",
                    "source": "real",
                    "mode": "motorcycle",
                    "state": self.state,
                    "revision": self.revision,
                    "route_generation": self.route_generation,
                    "route_reason": self.route_reason,
                    "repeat_serial": self.repeat_serial,
                    "progress_m": self.progress,
                    "fix": fix,
                    "results": self.results,
                    "route": self.route,
                    "preview": self.preview,
                    "next_turn": next_turn,
                    "remaining_m": round(remaining) if remaining is not None else None,
                    "remaining_s": round(seconds) if seconds is not None else None,
                    "notice": self.notice,
                    "note": (
                        "Real OSM route; device location accuracy varies. "
                        "ETA excludes live traffic."
                    ),
                }
            )

    def summary(self):
        data = self.snapshot()
        if data["fix"]:
            data["fix"] = {key: value for key, value in data["fix"].items() if key != "point"}
        data["results"] = [self._place_summary(place) for place in data["results"]]
        for key in ("route", "preview"):
            if data[key]:
                route = data[key]
                data[key] = {
                    field: route[field]
                    for field in (
                        "destination",
                        "destination_id",
                        "preference",
                        "distance_m",
                        "duration_s",
                        "has_highway",
                        "has_toll",
                        "provider",
                        "traffic_aware",
                    )
                }
                data[key]["stop"] = (
                    self._place_summary(route["stop_place"]) if route["stop_place"] else None
                )
        return data

    def action(self, name, parameters, hud):
        if name not in ("plan", "control", "stop", "search"):
            raise ValueError("Unknown navigation action")
        getattr(self, name)(parameters)
        result = self.summary()
        result["hud"] = self.publish(hud)
        if name == "control" and parameters.get("action") in ("start", "resume", "reroute"):
            panel = hud.request("panel nav on")
            if panel.get("status") != "ok":
                result["hud"] = panel
        return result

    def publish(self, hud):
        data = self.snapshot()
        hud.request(map_command(data), timeout=0.3)
        turn = data["next_turn"] or {}
        label = (
            (turn.get("street") or (data["route"] or {}).get("destination", "No active route"))[:24]
            .encode("ascii", "replace")
            .hex()
        )
        return hud.request(
            f"nav_live {data['state']} {turn.get('maneuver', 'none')} "
            f"{turn.get('distance_m', -1)} "
            f"{data['remaining_m'] if data['remaining_m'] is not None else -1} "
            f"{data['remaining_s'] if data['remaining_s'] is not None else -1} {label}",
            timeout=0.3,
        )
