from fastapi import APIRouter, Query

from app.api.v1.deps import SessionDep
from app.core.constants import CATEGORIES
from app.core.exceptions import ValidationError
from app.domain.schemas.compare import CompareResponse, GotchasResponse
from app.domain.services.compare_service import compare_service

router = APIRouter()


def _norm(code: str) -> str:
    return code.strip().upper()


@router.get("/compare", response_model=CompareResponse)
async def compare(
    db: SessionDep,
    from_state: str = Query(..., min_length=2, max_length=2),
    to_state: str = Query(..., min_length=2, max_length=2),
    category: str | None = Query(None),
) -> CompareResponse:
    if category is not None and category not in CATEGORIES:
        raise ValidationError(f"category must be one of: {', '.join(CATEGORIES)}")
    return await compare_service.compare(
        db, _norm(from_state), _norm(to_state), category
    )


@router.get("/compare/gotchas", response_model=GotchasResponse)
async def gotchas(
    db: SessionDep,
    from_state: str = Query(..., min_length=2, max_length=2),
    to_state: str = Query(..., min_length=2, max_length=2),
) -> GotchasResponse:
    return await compare_service.gotchas(db, _norm(from_state), _norm(to_state))
