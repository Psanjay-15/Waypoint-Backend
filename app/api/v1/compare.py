from fastapi import APIRouter, Query

from app.core.exceptions import UnknownStateError
from app.db import states_col
from app.domain.dataset import area_profile

router = APIRouter()


@router.get("/compare")
async def compare(
    state: str = Query(..., description="Destination state code"),
    city: str | None = Query(None),
    area: str | None = Query(None),
) -> dict:
    """Area profile for a destination state/city/area (powers Home/Compare)."""
    doc = await states_col().find_one({"_id": state.strip().upper()})
    if doc is None:
        raise UnknownStateError(f"No data for state '{state}'")
    return area_profile(doc, city, area)
