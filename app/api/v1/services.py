from fastapi import APIRouter, Query

from app.core.exceptions import UnknownStateError
from app.db import states_col
from app.domain.dataset import services_directory

router = APIRouter()


@router.get("/services")
async def services(state: str = Query(...), city: str | None = Query(None)) -> dict:
    doc = await states_col().find_one({"_id": state.strip().upper()})
    if doc is None:
        raise UnknownStateError(f"No data for state '{state}'")
    return services_directory(doc, city)
