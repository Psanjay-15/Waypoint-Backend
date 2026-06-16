from __future__ import annotations

from pydantic import BaseModel, Field


class CityProfile(BaseModel):
    name: str
    population: str = Field(..., description="Approximate, e.g. '~960,000'")
    cost_index: int = Field(..., description="Cost of living, US average = 100")
    median_rent: int = Field(..., description="Typical monthly rent in USD")
    safety: str = Field(..., description="Short descriptor, e.g. 'Low crime'")
    job_market: str = Field(..., description="Short descriptor + key industries")
    climate: str = Field(..., description="Short descriptor")
    vibe: str = Field(..., description="Short descriptor, e.g. 'Lively, young, urban'")
    best_for: list[str] = Field(default_factory=list, description="Audience tags")
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)


class CityFinderResult(BaseModel):
    """LLM structured output: cities to consider in the chosen state."""

    overview: str = Field(..., description="2-4 sentences guiding the city choice.")
    cities: list[CityProfile]


class CityFinderResponse(BaseModel):
    state: str
    overview: str
    cities: list[CityProfile]
    disclaimer: str
