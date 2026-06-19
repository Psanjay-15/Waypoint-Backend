from fastapi import APIRouter

from app.core.exceptions import UnknownStateError
from app.db import states_col

router = APIRouter()


@router.get("/states")
async def list_states() -> list[dict]:
    cur = states_col().find({}, {"name": 1}).sort("name", 1)
    return [{"code": d["_id"], "name": d["name"]} async for d in cur]


@router.get("/states/{code}")
async def get_state(code: str) -> dict:
    doc = await states_col().find_one({"_id": code.strip().upper()})
    if doc is None:
        raise UnknownStateError(f"No data for state '{code}'")
    doc.pop("_id", None)
    return doc
