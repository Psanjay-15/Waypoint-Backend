from fastapi import APIRouter, Query

from app.core.exceptions import UnknownStateError
from app.db import states_col
from app.domain.dataset import cities_overview

router = APIRouter()


@router.get("/cities")
async def cities(state: str = Query(...)) -> dict:
    doc = await states_col().find_one({"_id": state.strip().upper()})
    if doc is None:
        raise UnknownStateError(f"No data for state '{state}'")
    return cities_overview(doc)
