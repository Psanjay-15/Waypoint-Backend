from fastapi import APIRouter
from pydantic import BaseModel

from app.core.exceptions import UnknownStateError
from app.db import states_col
from app.domain.dataset import cost_compare

router = APIRouter()


class CostRequest(BaseModel):
    fromState: str
    toState: str
    salary: float
    filing: str = "single"
    housing: str = "rent"
    homeValue: float | None = None
    monthlySpending: float | None = None
    city: str | None = None


@router.post("/cost")
async def cost(body: CostRequest) -> dict:
    f = await states_col().find_one({"_id": body.fromState.strip().upper()})
    t = await states_col().find_one({"_id": body.toState.strip().upper()})
    if f is None or t is None:
        raise UnknownStateError("No cost data for one of the selected states")
    return cost_compare(f, t, body.model_dump())
