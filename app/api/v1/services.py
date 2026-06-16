from fastapi import APIRouter, Query

from app.api.v1.deps import SessionDep
from app.core.exceptions import UnknownStateError, ValidationError
from app.db.repositories.state_repo import state_repo
from app.domain.schemas.services import ServicesResponse
from app.domain.services.providers_service import (
    CATEGORIES,
    providers_service,
    supported_categories,
)

router = APIRouter()

RADIUS_MIN = 1000
RADIUS_MAX = 40000


@router.get("/services", response_model=ServicesResponse)
async def services(
    db: SessionDep,
    to_state: str = Query(..., description="Destination state code, e.g. TX"),
    city: str | None = Query(None, description="City; defaults to the state capital"),
    categories: str | None = Query(
        None, description="Comma-separated, e.g. movers,plumber"
    ),
    radius: int = Query(15000, description="Search radius in meters (max 40000)"),
) -> ServicesResponse:
    code = to_state.strip().upper()
    state = await state_repo.get(db, code)
    if state is None:
        raise UnknownStateError(f"Unknown or unsupported state '{code}'")

    cats: list[str] = []
    if categories:
        cats = [c.strip().lower() for c in categories.split(",") if c.strip()]
        invalid = [c for c in cats if c not in CATEGORIES]
        if invalid:
            raise ValidationError(
                f"Unsupported categories {invalid}. Choose from: {', '.join(CATEGORIES)}"
            )

    radius = max(RADIUS_MIN, min(RADIUS_MAX, radius))
    target_city = (city or state.capital).strip()
    return await providers_service.find(code, state.name, target_city, cats, radius)


@router.get("/services/categories")
async def services_categories() -> dict[str, list[dict]]:
    return {"categories": supported_categories()}
