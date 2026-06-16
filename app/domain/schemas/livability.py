from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.domain.schemas.chat import _normalize_state


class SafetyScore(BaseModel):
    state_code: str
    state_name: str
    violent_per_100k: int
    property_per_100k: int
    score: int
    grade: str
    vs_national: str
    source: str
    source_url: str
    year: int


class CityRent(BaseModel):
    city: str
    median_rent: int


class CityFit(BaseModel):
    """Who a place suits, grounded in the provided safety + rent numbers."""

    summary: str = Field(
        ..., description="2-4 sentences on what living here is like and who it suits."
    )
    best_for: list[str] = Field(
        default_factory=list,
        description="Short tags, e.g. 'Families', 'Young professionals', 'Retirees', 'Students'.",
    )


class LivabilityRequest(BaseModel):
    from_state: str
    to_state: str

    _norm_from = field_validator("from_state", mode="before")(_normalize_state)
    _norm_to = field_validator("to_state", mode="before")(_normalize_state)


class LivabilityResponse(BaseModel):
    from_safety: SafetyScore
    to_safety: SafetyScore
    safer_move: bool
    rent_state: str
    rent_source: str
    rent_source_url: str
    city_rents: list[CityRent]
    fit: CityFit | None = None
    fit_available: bool = False
    disclaimer: str
