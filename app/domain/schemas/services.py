from __future__ import annotations

from pydantic import BaseModel


class ProviderOut(BaseModel):
    """One local service business, normalized from Yelp."""

    id: str
    name: str
    category: str
    rating: float | None = None
    review_count: int = 0
    phone: str | None = None
    address: str | None = None
    website: str | None = None
    directions_url: str
    distance_m: int | None = None


class ServiceGroup(BaseModel):
    category: str
    label: str
    providers: list[ProviderOut]


class ServicesResponse(BaseModel):
    state: str
    city: str
    groups: list[ServiceGroup]
    count: int
    attribution: str = "Map data © OpenStreetMap contributors"
