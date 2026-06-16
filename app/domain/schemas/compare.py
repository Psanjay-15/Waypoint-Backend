from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict


class FactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    state_code: str
    category: str
    title: str
    summary: str
    details: str | None = None
    value_structured: dict[str, Any] | None = None
    is_gotcha: bool
    source_url: str
    source_name: str
    last_verified: date

    @classmethod
    def from_orm_fact(cls, fact) -> "FactOut":
        return cls(
            id=str(fact.id),
            state_code=fact.state_code,
            category=fact.category,
            title=fact.title,
            summary=fact.summary,
            details=fact.details,
            value_structured=fact.value_structured,
            is_gotcha=fact.is_gotcha,
            source_url=fact.source_url,
            source_name=fact.source_name,
            last_verified=fact.last_verified,
        )


class ComparisonRow(BaseModel):
    comparable_key: str
    category: str
    title: str
    from_fact: FactOut | None = None
    to_fact: FactOut | None = None


class CompareResponse(BaseModel):
    from_state: str
    to_state: str
    category: str | None = None
    rows: list[ComparisonRow]
    disclaimer: str


class GotchasResponse(BaseModel):
    from_state: str
    to_state: str
    gotchas: list[FactOut]
    disclaimer: str
