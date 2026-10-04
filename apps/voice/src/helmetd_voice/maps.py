"""Small, rate-limited public OSM adapters for the local MVP; no user-location logs."""

import copy
import json
import math
import os
import threading
import time
from collections import OrderedDict

import httpx

CATEGORIES = {"fuel": "fuel", "coffee": "cafe", "food": "restaurant", "parking": "parking"}


def coordinate(lat, lon):
    if (
        type(lat) not in (int, float)
        or type(lon) not in (int, float)
        or not math.isfinite(lat)
        or not math.isfinite(lon)
        or not -85 <= lat <= 85
        or not -180 <= lon <= 180
    ):
        raise ValueError("Invalid map coordinates")
    return [float(lat), float(lon)]


def distance(a, b):
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    delta = math.radians(b[1] - a[1])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta / 2) ** 2
    )
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def decode_shape(encoded):
    if not isinstance(encoded, str) or len(encoded) > 300000:
        raise ValueError("Invalid route geometry")
    point, index, result = [0, 0], 0, []
    while index < len(encoded):
        for axis in (0, 1):
            value, shift = 0, 0
            while True:
                if index >= len(encoded) or shift > 30:
                    raise ValueError("Invalid route geometry")
                byte = ord(encoded[index]) - 63
                index += 1
                if not 0 <= byte <= 63:
                    raise ValueError("Invalid route geometry")
                value |= (byte & 31) << shift
                shift += 5
                if byte < 32:
                    break
            point[axis] += ~(value >> 1) if value & 1 else value >> 1
        result.append(coordinate(point[0] / 1e6, point[1] / 1e6))
    return result


class Maps:
    def __init__(self, transport=None):
        self.transport = transport
        self.lock = threading.Lock()
        self.next_request = 0
        self.cache = OrderedDict()
        self.router = os.getenv("HELMETD_ROUTING_URL", "https://valhalla1.openstreetmap.de").rstrip(
            "/"
        )
        self.geocoder = os.getenv("HELMETD_GEOCODER_URL", "https://photon.komoot.io").rstrip("/")
        self.overpass = os.getenv("HELMETD_OVERPASS_URL", "https://overpass-api.de/api/interpreter")

    def request(self, method, url, *, params=None, body=None, form=None):
        key = json.dumps([method, url, params, body, form], sort_keys=True)
        # Serialize public-provider requests, cap rate, cache repeats only in memory.
        with self.lock:
            now = time.monotonic()
            if key in self.cache and now - self.cache[key][0] < 120:
                self.cache.move_to_end(key)
                return copy.deepcopy(self.cache[key][1])
            if self.transport is None:
                time.sleep(max(0, self.next_request - now))
            self.next_request = time.monotonic() + 1.05
            try:
                with httpx.Client(
                    timeout=20,
                    transport=self.transport,
                    headers={
                        "User-Agent": "Helmetd-local-navigation-MVP/0.1",
                        "X-Client-Id": "helmetd-local-mvp",
                    },
                ) as client:
                    response = client.request(method, url, params=params, json=body, data=form)
                    response.raise_for_status()
                    if len(response.content) > 4_000_000:
                        raise ValueError("Map response was too large")
                    result = response.json()
            except (httpx.HTTPError, ValueError):
                raise ValueError("The map service is unavailable. Try again shortly.") from None
            self.cache[key] = time.monotonic(), result
            while len(self.cache) > 32:
                self.cache.popitem(last=False)
            return copy.deepcopy(result)

    def search(self, query, origin):
        query = query.strip()
        if not 1 <= len(query) <= 160:
            raise ValueError("Enter a destination or choose a nearby category")
        lat, lon = coordinate(*origin)
        category = query.lower()
        brand = category.replace("’", "'").replace("'", "") in ("mcdonalds", "mcdonalds restaurant")
        if category in CATEGORIES or brand:
            amenity = "fast_food" if brand else CATEGORIES[category]
            brand_filter = '["brand"~"McDonald",i]' if brand else ""
            data = self.request(
                "POST",
                self.overpass,
                form={
                    "data": (
                        f'[out:json][timeout:15];nwr["amenity"="{amenity}"]{brand_filter}'
                        f"(around:5000,{lat},{lon});out center tags 250;"
                    )
                },
            )
            places = []
            for element in data.get("elements", []):
                tags = element.get("tags", {})
                center = element.get("center", element)
                try:
                    point = coordinate(center["lat"], center["lon"])
                except (KeyError, ValueError):
                    continue
                name = (
                    tags.get("name") or tags.get("brand") or f"{category.title()} (unnamed in OSM)"
                )
                address = " ".join(
                    str(tags.get(key, ""))
                    for key in ("addr:housenumber", "addr:street", "addr:city")
                ).strip()
                places.append(
                    {
                        "id": f"osm-{element['type']}-{element['id']}",
                        "name": str(name)[:120],
                        "address": address[:240],
                        "point": point,
                        "category": category,
                    }
                )
        else:
            dy, dx = 0.23, min(2, 0.23 / max(0.15, math.cos(math.radians(lat))))
            data = self.request(
                "GET",
                self.geocoder + "/api/",
                params={
                    "q": query,
                    "lat": lat,
                    "lon": lon,
                    "limit": 8,
                    "bbox": (
                        f"{max(-180, lon - dx)},{max(-85, lat - dy)},"
                        f"{min(180, lon + dx)},{min(85, lat + dy)}"
                    ),
                },
            )
            places = []
            for feature in data.get("features", []):
                props = feature.get("properties", {})
                try:
                    lng, latitude = feature["geometry"]["coordinates"][:2]
                    point = coordinate(latitude, lng)
                except (KeyError, ValueError, TypeError):
                    continue
                address = ", ".join(
                    str(props[key]) for key in ("street", "city", "state") if props.get(key)
                )
                places.append(
                    {
                        "id": f"osm-{props.get('osm_type')}-{props.get('osm_id')}",
                        "name": str(props.get("name") or props.get("street") or query)[:120],
                        "address": address[:240],
                        "point": point,
                        "category": "place",
                    }
                )
        unique = {}
        for place in places:
            place["distance_m"] = round(distance(origin, place["point"]))
            if place["distance_m"] <= (5100 if category in CATEGORIES else 25000):
                unique[place["id"]] = place
        return sorted(unique.values(), key=lambda place: place["distance_m"])[:8]

    def route(self, origin, destination, preference="fastest", stop=None):
        if preference not in ("fastest", "avoid_highways"):
            raise ValueError("Choose fastest or prefer local roads")
        points = [coordinate(*origin)] + ([stop["point"]] if stop else []) + [destination["point"]]
        data = self.request(
            "POST",
            self.router + "/route",
            body={
                "locations": [{"lat": p[0], "lon": p[1], "type": "break"} for p in points],
                "costing": "motorcycle",
                "costing_options": {
                    "motorcycle": {
                        "use_highways": 0 if preference == "avoid_highways" else 1,
                        "use_trails": 0,
                    }
                },
                "directions_options": {"units": "kilometers", "language": "en-US"},
            },
        )
        try:
            trip = data["trip"]
            if trip["status"] != 0:
                raise ValueError
            shape, maneuvers = [], []
            for leg_index, leg in enumerate(trip["legs"]):
                geometry = decode_shape(leg["shape"])
                offset = len(shape)
                shape.extend(geometry)
                for m in leg["maneuvers"]:
                    begin, end = int(m["begin_shape_index"]), int(m["end_shape_index"])
                    if not 0 <= begin <= end < len(geometry):
                        raise ValueError
                    maneuvers.append(
                        {
                            "instruction": str(m["instruction"])[:400],
                            "street": str((m.get("street_names") or m.get("begin_street_names") or [""])[0])[:120],
                            "type": int(m["type"]),
                            "begin": offset + begin,
                            "end": offset + end,
                            "duration_s": float(m.get("time", 0)),
                            "stop": bool(stop and leg_index == 0 and m["type"] in (4, 5, 6)),
                        }
                    )
            cumulative = [0.0]
            for a, b in zip(shape, shape[1:]):
                cumulative.append(cumulative[-1] + distance(a, b))
            if len(shape) < 2 or len(shape) > 25000 or cumulative[-1] <= 0:
                raise ValueError
            summary = trip["summary"]
            seconds = float(summary["time"])
            length = float(summary["length"])
            if (
                not maneuvers
                or not math.isfinite(seconds)
                or not 0 <= seconds <= 604800
                or not math.isfinite(length)
                or not 0 < length <= 10000
            ):
                raise ValueError
            return {
                "destination": destination["name"],
                "destination_id": destination["id"],
                "destination_place": copy.deepcopy(destination),
                "stop_place": copy.deepcopy(stop),
                "preference": preference,
                "geometry": shape,
                "cumulative": cumulative,
                "maneuvers": maneuvers,
                "distance_m": round(length * 1000),
                "duration_s": round(seconds),
                "has_highway": bool(summary.get("has_highway")),
                "has_toll": bool(summary.get("has_toll")),
                "origin": list(origin),
                "provider": "Valhalla / FOSSGIS",
                "traffic_aware": False,
            }
        except (KeyError, TypeError, ValueError, IndexError):
            raise ValueError(
                "No usable motorcycle route was returned. Choose another destination."
            ) from None
