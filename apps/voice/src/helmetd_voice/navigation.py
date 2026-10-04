"""Shared navigation state for the Mac bench. All roads and positions are synthetic.

The assistant requests transitions; this engine owns routing, distance, and arrival.
No geographic coordinates, routing provider, or live GPS are implied by this demo.
"""

import heapq
import copy
import math
import threading
import time

NODES = {
    "garage": (80, 360),
    "market": (260, 360),
    "fuel": (260, 200),
    "ridge": (500, 200),
    "lookout": (660, 80),
    "cafe": (500, 360),
    "east": (660, 360),
}
PLACES = {"garage": "Garage", "lookout": "Ridge Lookout", "cafe": "Coffee Stop", "fuel": "Fuel Stop"}
# Endpoints, name, synthetic speed (m/s), highway. Drawing units = four demo metres.
ROADS = [
    ("garage", "market", "Workshop Road", 12, False),
    ("market", "fuel", "Market Street", 10, False),
    ("fuel", "ridge", "Ridge Road", 10, False),
    ("ridge", "lookout", "Lookout Road", 10, False),
    ("market", "cafe", "Expressway", 24, True),
    ("cafe", "east", "East Road", 16, False),
    ("east", "lookout", "Lake Road", 16, False),
    ("cafe", "ridge", "Hill Street", 14, False),
]


def metres(a, b):
    return math.dist(a, b) * 4


def route_between(origin, destination, preference):
    """Dijkstra on a tiny authored road network, splitting the current road at origin."""
    points = {**NODES, "origin": tuple(origin)}
    edges = []
    nearest = None
    for a, b, street, speed, highway in ROADS:
        p, q = NODES[a], NODES[b]
        delta = (q[0] - p[0], q[1] - p[1])
        t = max(0, min(1, sum((origin[i] - p[i]) * delta[i] for i in (0, 1)) / sum(
            v * v for v in delta
        )))
        projected = tuple(p[i] + t * delta[i] for i in (0, 1))
        candidate = (math.dist(origin, projected), a, b, street, speed, highway, projected)
        if nearest is None or candidate[0] < nearest[0]:
            nearest = candidate
        if preference != "avoid_highways" or not highway:
            edges.append((a, b, street, speed))
    _, a, b, street, speed, highway, projected = nearest
    points["origin"] = projected
    # If already on a highway, allow leaving it even when avoiding new highways.
    edges.extend([("origin", a, street, speed), ("origin", b, street, speed)])
    graph = {node: [] for node in points}
    for a, b, street, speed in edges:
        for start, end in ((a, b), (b, a)):
            length = metres(points[start], points[end])
            graph[start].append((end, length / speed, street, length))
    queue, best = [(0, "origin", [])], {"origin": 0}
    while queue:
        duration, node, legs = heapq.heappop(queue)
        if duration != best[node]:
            continue
        if node == destination:
            return legs
        for end, seconds, street, length in graph[node]:
            cost = duration + seconds
            if cost >= best.get(end, math.inf):
                continue
            best[end] = cost
            leg = {"a": points[node], "b": points[end], "street": street,
                   "distance_m": length, "duration_s": seconds, "end_node": end}
            heapq.heappush(queue, (cost, end, legs + ([leg] if length > 0.01 else [])))
    raise ValueError("No demo route is available")


class Navigation:
    def __init__(self, clock=time.monotonic):
        self.lock = threading.RLock()
        self.clock = clock
        self.last_tick = clock()
        self.seen = clock()
        self.location = NODES["garage"]
        self.state = "idle"
        self.route = None
        self.preview = None
        self.index = 0
        self.progress = 0.0
        self.playing = False
        self.revision = 0
        self.notice = "Choose a destination to preview a demo route."
        self.before_loss = "idle"

    @staticmethod
    def resolve(query):
        if not isinstance(query, str) or len(query) > 120:
            raise ValueError("Choose a demo destination")
        query = query.strip().lower()
        aliases = {"home": "garage", "workshop": "garage", "lookout": "lookout",
                   "coffee": "cafe", "cafe": "cafe", "fuel": "fuel", "gas": "fuel"}
        if query in aliases:
            return aliases[query]
        for key, label in PLACES.items():
            if query in (key, label.lower()):
                return key
        raise ValueError("Only demo destinations are available: Garage, Ridge Lookout, "
                         "Coffee Stop, or Fuel Stop. Real place search is not connected.")

    def _build(self, destination, preference, stop=None):
        if preference not in ("fastest", "avoid_highways"):
            raise ValueError("Choose fastest or avoid_highways")
        if stop and metres(self.location, NODES[stop]) < 1:
            stop = None
        legs = route_between(self.location, stop or destination, preference)
        if stop and stop != destination:
            if legs:
                legs[-1] = {**legs[-1], "stop": PLACES[stop]}
            legs += route_between(NODES[stop], destination, preference)
        return {"destination_id": destination, "destination": PLACES[destination],
                "preference": preference, "stop_id": stop, "legs": legs}

    def plan(self, p):
        destination = self.resolve(p.get("destination"))
        preference = p.get("preference", "fastest")
        with self.lock:
            if self.state == "location_lost":
                raise ValueError("Restore the demo location before planning a route")
            self.preview = self._build(destination, preference)
            self.revision += 1
            self.notice = "Preview ready. Start to accept this route."
            return self.snapshot()

    def stop(self, p):
        with self.lock:
            current = self.preview or self.route
            if not current:
                raise ValueError("Choose a destination before adding or removing a stop")
            if self.state == "location_lost":
                raise ValueError("Restore the demo location before changing the route")
            action = p.get("action")
            if action not in ("add", "remove"):
                raise ValueError("Choose add or remove")
            stop = self.resolve(p.get("place")) if action == "add" else None
            if stop == current["destination_id"]:
                raise ValueError("That place is already the destination")
            self.preview = self._build(current["destination_id"], current["preference"], stop)
            self.revision += 1
            self.notice = "Updated preview ready. Start to accept the change."
            return self.snapshot()

    def control(self, p):
        action = p.get("action")
        with self.lock:
            if action == "cancel_preview":
                self.preview = None
                self.notice = "Preview dismissed."
            elif action == "cancel":
                self.route = self.preview = None
                self.state, self.playing = "idle", False
                self.notice = "Navigation cancelled."
            elif action == "start":
                if self.state == "location_lost":
                    raise ValueError("Restore the demo location before starting")
                if not self.preview:
                    if self.state == "navigating":
                        return self.snapshot()
                    raise ValueError("Preview a destination first")
                preview = self.preview
                self.route = self._build(preview["destination_id"], preview["preference"],
                                         preview["stop_id"])
                self.preview = None
                self.index, self.progress = 0, 0.0
                self.state, self.playing = "navigating", False
                self.notice = "Demo navigation started. Use Play demo or Next turn to move."
                self._arrive_if_done()
            elif action == "pause":
                if self.state not in ("navigating", "paused"):
                    raise ValueError("There is no running route to pause")
                self.state, self.playing = "paused", False
                self.notice = "Navigation paused."
            elif action == "resume":
                if self.state not in ("paused", "navigating"):
                    raise ValueError("There is no paused route to resume")
                self.state = "navigating"
                self.notice = "Navigation resumed."
            elif action == "reroute":
                if not self.route or self.state not in ("off_route", "navigating", "paused"):
                    raise ValueError("A route and a usable demo location are required")
                self.route = self._build(self.route["destination_id"], self.route["preference"],
                                         self.route["stop_id"])
                self.index, self.progress = 0, 0.0
                self.preview = None
                self.state, self.playing = "navigating", False
                self.notice = "Route recalculated from the demo position."
                self._arrive_if_done()
            elif action == "repeat":
                return self.snapshot()
            else:
                raise ValueError("Unknown navigation action")
            self.revision += 1
            return self.snapshot()

    def _arrive_if_done(self):
        if self.route and self.index >= len(self.route["legs"]):
            self.state, self.playing = "arrived", False
            self.location = NODES[self.route["destination_id"]]
            self.notice = f"Arrived at {self.route['destination']} in the demo."

    def _advance(self, distance):
        while self.state == "navigating" and distance > 0:
            leg = self.route["legs"][self.index]
            step = min(distance, leg["distance_m"] - self.progress)
            self.progress += step
            distance -= step
            ratio = self.progress / leg["distance_m"]
            self.location = tuple(leg["a"][i] + (leg["b"][i] - leg["a"][i]) * ratio
                                  for i in (0, 1))
            if self.progress >= leg["distance_m"] - 0.001:
                self.index += 1
                self.progress = 0.0
                if leg.get("stop"):
                    self.route["stop_id"] = None
                    self.state, self.playing = "paused", False
                    self.notice = f"Demo stop reached: {leg['stop']}. Resume when ready."
                self._arrive_if_done()
            self.revision += 1

    def demo(self, p):
        """Operator-only simulation controls, deliberately absent from AI tools."""
        event = p.get("event")
        with self.lock:
            if event == "reset":
                self.location = NODES["garage"]
                self.route = self.preview = None
                self.state, self.playing = "idle", False
                self.notice = "Demo reset to Garage."
            elif event == "restore_location":
                if self.state != "location_lost":
                    raise ValueError("Demo location is already available")
                self.state = "off_route" if self.before_loss == "off_route" else "paused"
                self.notice = ("Demo location restored. Reroute to continue." if
                               self.state == "off_route" else
                               "Demo location restored. Resume when ready.")
            elif event == "lose_location":
                if self.state not in ("navigating", "paused", "off_route"):
                    raise ValueError("Start a route before testing location loss")
                self.before_loss = self.state
                self.state, self.playing = "location_lost", False
                self.preview = None
                self.notice = "Location unavailable. Turn guidance is suspended."
            elif event == "play":
                if self.state != "navigating":
                    raise ValueError("Start or resume navigation first")
                self.playing = not self.playing
                self.seen, self.last_tick = self.clock(), self.clock()
                self.notice = "Playing demo at 4x." if self.playing else "Demo movement paused."
            elif event == "next_turn":
                if self.state != "navigating":
                    raise ValueError("Start or resume navigation first")
                self._advance(self.route["legs"][self.index]["distance_m"] - self.progress)
            elif event == "miss_turn":
                if self.state != "navigating":
                    raise ValueError("Start or resume navigation first")
                node = self.route["legs"][self.index]["end_node"]
                planned = (self.route["legs"][self.index + 1]["end_node"]
                           if self.index + 1 < len(self.route["legs"]) else None)
                neighbours = [b if a == node else a for a, b, *_ in ROADS if node in (a, b)]
                wrong = next((n for n in neighbours if n != planned), None)
                if wrong is None:
                    raise ValueError("No alternate junction is available here")
                self.location = NODES[wrong]
                self.state, self.playing = "off_route", False
                self.preview = None
                self.notice = "Missed turn simulated. Reroute from this demo position."
            else:
                raise ValueError("Unknown demo event")
            self.revision += 1
            return self.snapshot()

    def tick(self):
        with self.lock:
            now = self.clock()
            elapsed, self.last_tick = min(1, max(0, now - self.last_tick)), now
            if self.playing and now - self.seen > 5:
                self.playing = False
                self.notice = "Demo movement paused because the console disconnected."
            if self.playing and self.state == "navigating":
                leg = self.route["legs"][self.index]
                self._advance(elapsed * 4 * leg["distance_m"] / leg["duration_s"])

    def touch(self):
        with self.lock:
            self.seen = self.clock()

    def snapshot(self):
        with self.lock:
            available = self.state not in ("location_lost", "off_route")
            current = self.route
            step, remaining, seconds = None, None, None
            if current and available:
                legs = current["legs"][self.index:]
                remaining = max(0, sum(l["distance_m"] for l in legs) - self.progress)
                seconds = sum(l["duration_s"] for l in legs)
                if legs:
                    leg = legs[0]
                    seconds -= leg["duration_s"] * self.progress / leg["distance_m"]
                    maneuver, instruction = "arrive", f"Arrive at {current['destination']}"
                    if leg.get("stop"):
                        maneuver, instruction = "stop", f"Stop at {leg['stop']}"
                    elif len(legs) > 1:
                        next_leg = legs[1]
                        heading = lambda l: math.atan2(l["b"][0] - l["a"][0],
                                                      l["a"][1] - l["b"][1])
                        angle = (heading(next_leg) - heading(leg) + math.pi) % (2 * math.pi) - math.pi
                        maneuver = ("uturn" if abs(angle) > 2.5 else "straight"
                                    if abs(angle) < 0.5 else "right" if angle > 0 else "left")
                        verb = {"uturn": "Make a U-turn", "straight": "Continue straight",
                                "right": "Turn right", "left": "Turn left"}[maneuver]
                        instruction = f"{verb} onto {next_leg['street']}"
                    step = {"maneuver": maneuver, "instruction": instruction,
                            "street": leg["street"],
                            "distance_m": round(max(0, leg["distance_m"] - self.progress))}
            preview = None
            if self.preview:
                preview = {**self.preview,
                           "distance_m": round(sum(l["distance_m"] for l in self.preview["legs"])),
                           "duration_s": round(sum(l["duration_s"] for l in self.preview["legs"]))}
            return {"status": "ok", "source": "simulation", "mode": "motorcycle",
                    "state": self.state, "revision": self.revision, "playing": self.playing,
                    "location": self.location if self.state != "location_lost" else None,
                    "route": copy.deepcopy(current), "preview": copy.deepcopy(preview),
                    "next_turn": step,
                    "remaining_m": round(remaining) if remaining is not None else None,
                    "remaining_s": round(seconds) if seconds is not None else None,
                    "notice": self.notice,
                    "note": "Fictional roads and simulated movement. No GPS or live routing."}

    def summary(self):
        data = self.snapshot()
        for key in ("route", "preview"):
            if data[key]:
                data[key] = {k: v for k, v in data[key].items() if k != "legs"}
        data.pop("location")
        return data

    def action(self, name, parameters, hud):
        if name not in ("plan", "control", "stop"):
            raise ValueError("Unknown navigation action")
        getattr(self, name)(parameters)
        panel = None
        if name == "control" and parameters.get("action") in ("start", "resume", "reroute"):
            panel = hud.request("panel nav on")
        result = self.summary()
        result["hud"] = self.publish(hud)
        if panel and panel.get("status") != "ok":
            result["hud"] = panel
        result["hud_note"] = "Route state is local. Claim HUD display only if its status is ok."
        return result

    def publish(self, hud):
        data = self.snapshot()
        step = data["next_turn"] or {}
        destination = (data["route"] or {}).get("destination", "No active route")
        # Fixed bounded text protocol: names never become socket commands.
        label = destination[:24].encode("ascii", "replace").hex()
        command = (f"nav {data['state']} {step.get('maneuver', 'none')} "
                   f"{step.get('distance_m', -1)} "
                   f"{data['remaining_m'] if data['remaining_m'] is not None else -1} "
                   f"{data['remaining_s'] if data['remaining_s'] is not None else -1} {label}")
        return hud.request(command, timeout=0.3)
