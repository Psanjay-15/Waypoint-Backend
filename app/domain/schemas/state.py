from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    capital: str


class CategorySummary(BaseModel):
    category: str
    fact_count: int
    gotcha_count: int


class StateDetailResponse(BaseModel):
    code: str
    name: str
    capital: str
    categories: list[CategorySummary]
