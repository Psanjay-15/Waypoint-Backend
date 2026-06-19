from fastapi import APIRouter, Query

from app.core.exceptions import UnknownStateError
from app.db import states_col
from app.domain.dataset import safety_report

router = APIRouter()


@router.get("/safety")
async def safety(state: str = Query(...)) -> dict:
    doc = await states_col().find_one({"_id": state.strip().upper()})
    if doc is None:
        raise UnknownStateError(f"No data for state '{state}'")
    return safety_report(doc)
