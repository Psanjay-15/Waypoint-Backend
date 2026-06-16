from fastapi import APIRouter, Query

from app.core.exceptions import UnknownStateError
from app.domain.schemas.livability import LivabilityResponse
from app.domain.services.livability_service import livability_service

router = APIRouter()


@router.get("/livability", response_model=LivabilityResponse)
async def livability(
    from_state: str = Query(..., description="Origin state code, e.g. CA"),
    to_state: str = Query(..., description="Destination state code, e.g. TX"),
) -> LivabilityResponse:
    f = from_state.strip().upper()
    t = to_state.strip().upper()
    if not livability_service.supported(f):
        raise UnknownStateError(f"No livability data for state '{f}'")
    if not livability_service.supported(t):
        raise UnknownStateError(f"No livability data for state '{t}'")
    return await livability_service.assess(f, t)
