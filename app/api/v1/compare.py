from fastapi import APIRouter, Query

from app.core.exceptions import UnknownStateError
from app.db import states_col
from app.domain.dataset import area_profile, compare_rules

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


@router.get("/compare/rules")
async def rules(
    from_state: str = Query(..., alias="from"),
    to_state: str = Query(..., alias="to"),
) -> dict:
    """Side-by-side relocation rules that change between two states."""
    f = await states_col().find_one({"_id": from_state.strip().upper()})
    t = await states_col().find_one({"_id": to_state.strip().upper()})
    if f is None or t is None:
        raise UnknownStateError("No data for one of the selected states")
    return compare_rules(f, t)
