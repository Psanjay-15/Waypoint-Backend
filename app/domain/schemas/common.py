from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class Citation(BaseModel):
    fact_id: str
    title: str
    source_url: str
    source_name: str
    last_verified: date | None = None
    page_number: int | None = None


class HealthResponse(BaseModel):
    status: str
    db: str
    qdrant: str
    version: str
