"""Local service-provider directory, backed by OpenStreetMap (Overpass).

Yelp/Google have richer service-business data but now require a billing card.
The only genuinely free, key-less sources are OSM-based, so we reuse the
Overpass infrastructure already built for the Explore map (geocode + query +
address parsing) and add service-oriented tags (craft=plumber, office=
moving_company, shop=hardware, ...). Stores are well covered; individual
tradespeople depend on community mapping, so some groups may be thin — handled
with honest empty states. Contact data comes only from OSM, never generated.
"""

from __future__ import annotations

import time

from app.core.logging import get_logger
from app.domain.schemas.services import ProviderOut, ServiceGroup, ServicesResponse
from app.domain.services.places_service import _haversine_m, places_service

log = get_logger(__name__)

PER_CATEGORY_LIMIT = 12
CACHE_TTL_SECONDS = 60 * 30

CATEGORIES: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "movers": (
        "Packers & Movers",
        [("office", "moving_company"), ("shop", "storage_rental")],
    ),
    "plumber": ("Plumbers", [("craft", "plumber")]),
    "electrician": ("Electricians", [("craft", "electrician")]),
    "cleaner": (
        "Cleaning & Laundry",
        [("shop", "laundry"), ("shop", "dry_cleaning"), ("craft", "cleaning")],
    ),
    "gardener": (
        "Landscaping & Garden",
        [("craft", "gardener"), ("shop", "garden_centre")],
    ),
    "handyman": (
        "Handyman & Hardware",
        [("craft", "handyman"), ("shop", "hardware"), ("shop", "doityourself")],
    ),
    "hvac": ("Heating & AC (HVAC)", [("craft", "hvac")]),
    "grocery": (
        "Grocery",
        [("shop", "supermarket"), ("shop", "convenience"), ("shop", "grocery")],
    ),
    "pharmacy": ("Pharmacy", [("amenity", "pharmacy")]),
    "locksmith": ("Locksmiths", [("shop", "locksmith"), ("craft", "locksmith")]),
    "internet": (
        "Internet & Telecom",
        [("office", "telecommunication"), ("shop", "mobile_phone")],
    ),
    "pestcontrol": ("Pest Control", [("craft", "pest_control")]),
}

DEFAULT_CATEGORIES = [
    "movers",
    "plumber",
    "electrician",
    "cleaner",
    "gardener",
    "handyman",
    "grocery",
    "pharmacy",
]

_cache: dict[str, tuple[float, object]] = {}


def supported_categories() -> list[dict]:
    return [{"key": k, "label": v[0]} for k, v in CATEGORIES.items()]


def _cache_get(key: str):
    hit = _cache.get(key)
    if hit and (time.time() - hit[0]) < CACHE_TTL_SECONDS:
        return hit[1]
    return None


def _cache_put(key: str, value: object) -> None:
    _cache[key] = (time.time(), value)


def _build_query(lat: float, lng: float, radius: int, categories: list[str]) -> str:
    seen: set[tuple[str, str]] = set()
    clauses: list[str] = []
    for cat in categories:
        for key, value in CATEGORIES[cat][1]:
            if (key, value) in seen:
                continue
            seen.add((key, value))
            for kind in ("node", "way"):
                clauses.append(
                    f'{kind}["{key}"="{value}"](around:{radius},{lat},{lng});'
                )
    return (
        f"[out:json][timeout:25];\n(\n{chr(10).join(clauses)}\n);\nout center tags 200;"
    )


def _classify(tags: dict, categories: list[str]) -> str | None:
    for cat in categories:
        for key, value in CATEGORIES[cat][1]:
            if tags.get(key) == value:
                return cat
    return None


class ProvidersService:
    async def find(
        self,
        state_code: str,
        state_name: str,
        city: str,
        categories: list[str],
        radius: int,
    ) -> ServicesResponse:
        cats = [
            c for c in (categories or DEFAULT_CATEGORIES) if c in CATEGORIES
        ] or DEFAULT_CATEGORIES
        cache_key = f"svc:{state_code}|{city}|{radius}|{','.join(sorted(cats))}".lower()
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        lat, lng = await places_service.geocode(city, state_name)
        elements = await places_service._overpass(_build_query(lat, lng, radius, cats))

        buckets: dict[str, list[ProviderOut]] = {c: [] for c in cats}
        seen: set[str] = set()
        for el in elements:
            tags = el.get("tags") or {}
            name = tags.get("name")
            if not name:
                continue
            cat = _classify(tags, cats)
            if cat is None or len(buckets[cat]) >= PER_CATEGORY_LIMIT:
                continue
            plat = el.get("lat") or (el.get("center") or {}).get("lat")
            plng = (
                el.get("lon")
                or (el.get("center") or {}).get("lng")
                or (el.get("center") or {}).get("lon")
            )
            osm_id = f"{el.get('type', 'node')}/{el.get('id')}"
            if osm_id in seen:
                continue
            seen.add(osm_id)
            directions = (
                f"https://www.google.com/maps/dir/?api=1&destination={plat},{plng}"
                if plat is not None and plng is not None
                else f"https://www.google.com/maps/search/?api=1&query={name.replace(' ', '+')}"
            )
            buckets[cat].append(
                ProviderOut(
                    id=osm_id,
                    name=name,
                    category=cat,
                    phone=tags.get("phone") or tags.get("contact:phone"),
                    address=places_service._address(tags),
                    website=tags.get("website") or tags.get("contact:website"),
                    directions_url=directions,
                    distance_m=_haversine_m(lat, lng, plat, plng)
                    if plat and plng
                    else None,
                )
            )

        groups = [
            ServiceGroup(
                category=c,
                label=CATEGORIES[c][0],
                providers=sorted(buckets[c], key=lambda p: p.distance_m or 0),
            )
            for c in cats
            if buckets[c]
        ]
        total = sum(len(g.providers) for g in groups)
        result = ServicesResponse(
            state=state_code, city=city, groups=groups, count=total
        )
        _cache_put(cache_key, result)
        log.info(
            "services %s/%s -> %d providers across %d groups",
            state_code,
            city,
            total,
            len(groups),
        )
        return result


providers_service = ProvidersService()
