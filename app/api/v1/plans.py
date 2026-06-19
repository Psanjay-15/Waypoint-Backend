from fastapi import APIRouter
from pydantic import BaseModel

from app.core.exceptions import UnknownStateError
from app.db import states_col
from app.domain.dataset import build_plan

router = APIRouter()


class Quiz(BaseModel):
    housing: str = "rent"
    ownsVehicle: bool = True
    hasKids: bool = False
    hasPets: bool = False
    hasJob: bool = True


class PlanRequest(BaseModel):
    fromState: str
    toState: str
    city: str | None = None
    moveDate: str  # YYYY-MM-DD
    quiz: Quiz = Quiz()


@router.post("/plan")
async def plan(body: PlanRequest) -> dict:
    to_doc = await states_col().find_one({"_id": body.toState.strip().upper()})
    if to_doc is None:
        raise UnknownStateError(f"No data for state '{body.toState}'")
    quiz = body.quiz.model_dump()
    quiz["_tax"] = to_doc["tax"]
    tasks = build_plan(to_doc["name"], body.city, body.moveDate, quiz)
    return {"tasks": tasks}
