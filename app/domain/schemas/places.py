from __future__ import annotations

from pydantic import BaseModel


class PlaceOut(BaseModel):
    """One nearby point of interest, normalized from OpenStreetMap."""

    osm_id: str
    name: str
    category: str
    lat: float
    lng: float
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    email: str | None = None
    directions_url: str
    distance_m: int | None = None


class ExploreResponse(BaseModel):
    state: str
    city: str
    center_lat: float
    center_lng: float
    radius_m: int
    categories: list[str]
    count: int
    places: list[PlaceOut]
    attribution: str = "Map data © OpenStreetMap contributors"
