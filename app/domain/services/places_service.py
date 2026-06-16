"""Nearby-places discovery for the destination city.

Uses only free, key-less OpenStreetMap services:
  - Nominatim  -> geocode "city, state" to a lat/lng center
  - Overpass    -> find points of interest (schools, hospitals, ...) around it

Both are public community servers, so we identify ourselves with a User-Agent,
cache aggressively in-memory (TTL), and keep result counts modest.
"""

from __future__ import annotations

import math
import time

import httpx

from app.core.exceptions import RetrievalError
from app.core.logging import get_logger
from app.domain.schemas.places import ExploreResponse, PlaceOut

log = get_logger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "StateShiftBot/0.1 (relocation helper; hackathon project)"

CATEGORY_TAGS: dict[str, list[tuple[str, str]]] = {
    "hospital": [
        ("amenity", "hospital"),
        ("amenity", "clinic"),
        ("amenity", "doctors"),
    ],
    "school": [
        ("amenity", "school"),
        ("amenity", "college"),
        ("amenity", "university"),
    ],
    "restaurant": [
        ("amenity", "restaurant"),
        ("amenity", "cafe"),
        ("amenity", "fast_food"),
    ],
    "hotel": [("tourism", "hotel"), ("tourism", "motel"), ("tourism", "guest_house")],
    "transit": [
        ("railway", "station"),
        ("public_transport", "station"),
        ("amenity", "bus_station"),
    ],
    "grocery": [("shop", "supermarket"), ("shop", "grocery")],
    "pharmacy": [("amenity", "pharmacy")],
    "fire": [("amenity", "fire_station")],
    "bank": [("amenity", "bank"), ("amenity", "atm")],
    "fuel": [("amenity", "fuel")],
    "park": [("leisure", "park")],
    "police": [("amenity", "police")],
}

DEFAULT_CATEGORIES = [
    "hospital",
    "school",
    "restaurant",
    "hotel",
    "transit",
    "grocery",
    "pharmacy",
]
PER_CATEGORY_LIMIT = 10
CACHE_TTL_SECONDS = 60 * 30

_cache: dict[str, tuple[float, object]] = {}


def supported_categories() -> list[str]:
    return list(CATEGORY_TAGS.keys())


def _cache_get(key: str):
    hit = _cache.get(key)
    if hit and (time.time() - hit[0]) < CACHE_TTL_SECONDS:
        return hit[1]
    return None


def _cache_put(key: str, value: object) -> None:
    _cache[key] = (time.time(), value)


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return int(r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


class PlacesService:
    async def geocode(self, city: str, state_name: str) -> tuple[float, float]:
        key = f"geo:{city}|{state_name}".lower()
        cached = _cache_get(key)
        if cached:
            return cached
        params = {"q": f"{city}, {state_name}, USA", "format": "json", "limit": 1}
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT}, timeout=20.0
        ) as client:
            try:
                resp = await client.get(NOMINATIM_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise RetrievalError(f"geocoding failed: {exc}") from exc
        if not data:
            raise RetrievalError(f"could not locate '{city}, {state_name}'")
        center = (float(data[0]["lat"]), float(data[0]["lon"]))
        _cache_put(key, center)
        return center

    def _build_query(
        self, lat: float, lng: float, radius: int, categories: list[str]
    ) -> str:
        clauses: list[str] = []
        for cat in categories:
            for key, value in CATEGORY_TAGS.get(cat, []):
                for kind in ("node", "way"):
                    clauses.append(
                        f'{kind}["{key}"="{value}"](around:{radius},{lat},{lng});'
                    )
        body = "\n".join(clauses)
        return f"[out:json][timeout:25];\n(\n{body}\n);\nout center tags 200;"

    def _classify(self, tags: dict[str, str]) -> str | None:
        for cat, pairs in CATEGORY_TAGS.items():
            for key, value in pairs:
                if tags.get(key) == value:
                    return cat
        return None

    @staticmethod
    def _address(tags: dict[str, str]) -> str | None:
        parts = [
            " ".join(
                p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p
            ),
            tags.get("addr:city"),
            tags.get("addr:state"),
            tags.get("addr:postcode"),
        ]
        out = ", ".join(p for p in parts if p)
        return out or None

    async def _overpass(self, query: str) -> list[dict]:
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT}, timeout=40.0
        ) as client:
            try:
                resp = await client.post(OVERPASS_URL, data={"data": query})
                resp.raise_for_status()
                return resp.json().get("elements", [])
            except (httpx.HTTPError, ValueError) as exc:
                raise RetrievalError(f"places lookup failed: {exc}") from exc

    async def explore(
        self,
        state_code: str,
        state_name: str,
        city: str,
        categories: list[str],
        radius: int,
    ) -> ExploreResponse:
        cats = categories or DEFAULT_CATEGORIES
        cache_key = (
            f"explore:{state_code}|{city}|{radius}|{','.join(sorted(cats))}".lower()
        )
        cached = _cache_get(cache_key)
        if cached:
            return cached

        lat, lng = await self.geocode(city, state_name)
        elements = await self._overpass(self._build_query(lat, lng, radius, cats))

        per_cat: dict[str, int] = {}
        seen: set[str] = set()
        places: list[PlaceOut] = []
        for el in elements:
            tags = el.get("tags") or {}
            name = tags.get("name")
            if not name:
                continue
            category = self._classify(tags)
            if category is None:
                continue
            if per_cat.get(category, 0) >= PER_CATEGORY_LIMIT:
                continue
            plat = el.get("lat") or (el.get("center") or {}).get("lat")
            plng = el.get("lon") or (el.get("center") or {}).get("lon")
            if plat is None or plng is None:
                continue
            osm_id = f"{el.get('type', 'node')}/{el.get('id')}"
            if osm_id in seen:
                continue
            seen.add(osm_id)
            per_cat[category] = per_cat.get(category, 0) + 1
            places.append(
                PlaceOut(
                    osm_id=osm_id,
                    name=name,
                    category=category,
                    lat=plat,
                    lng=plng,
                    address=self._address(tags),
                    phone=tags.get("phone") or tags.get("contact:phone"),
                    website=tags.get("website") or tags.get("contact:website"),
                    email=tags.get("email") or tags.get("contact:email"),
                    directions_url=f"https://www.google.com/maps/dir/?api=1&destination={plat},{plng}",
                    distance_m=_haversine_m(lat, lng, plat, plng),
                )
            )

        places.sort(key=lambda p: p.distance_m or 0)
        result = ExploreResponse(
            state=state_code,
            city=city,
            center_lat=lat,
            center_lng=lng,
            radius_m=radius,
            categories=cats,
            count=len(places),
            places=places,
        )
        _cache_put(cache_key, result)
        log.info(
            "explore %s/%s r=%dm -> %d places", state_code, city, radius, len(places)
        )
        return result


places_service = PlacesService()
