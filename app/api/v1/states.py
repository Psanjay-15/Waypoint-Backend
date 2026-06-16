from fastapi import APIRouter

from app.api.v1.deps import SessionDep
from app.core.exceptions import UnknownStateError
from app.db.repositories.law_fact_repo import law_fact_repo
from app.db.repositories.state_repo import state_repo
from app.domain.schemas.state import CategorySummary, StateDetailResponse, StateOut

router = APIRouter()


@router.get("/states", response_model=list[StateOut])
async def list_states(db: SessionDep) -> list[StateOut]:
    states = await state_repo.list_all(db)
    return [StateOut.model_validate(s) for s in states]


@router.get("/states/{code}", response_model=StateDetailResponse)
async def get_state(code: str, db: SessionDep) -> StateDetailResponse:
    code = code.strip().upper()
    state = await state_repo.get(db, code)
    if state is None:
        raise UnknownStateError(f"Unknown or unsupported state '{code}'")
    summaries = await law_fact_repo.category_summaries(db, code)
    return StateDetailResponse(
        code=state.code,
        name=state.name,
        capital=state.capital,
        categories=[CategorySummary(**s) for s in summaries],
    )
