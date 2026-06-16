from fastapi import APIRouter, Query

from app.api.v1.deps import SessionDep
from app.core.exceptions import UnknownStateError, ValidationError
from app.db.repositories.state_repo import state_repo
from app.domain.schemas.places import ExploreResponse
from app.domain.services.places_service import places_service, supported_categories

router = APIRouter()

RADIUS_MIN = 500
RADIUS_MAX = 20000


@router.get("/explore", response_model=ExploreResponse)
async def explore(
    db: SessionDep,
    to_state: str = Query(..., description="Destination state code, e.g. TX"),
    city: str | None = Query(
        None, description="City to explore; defaults to the state capital"
    ),
    categories: str | None = Query(
        None, description="Comma-separated, e.g. hospital,school,transit"
    ),
    radius: int = Query(5000, description="Search radius in meters"),
) -> ExploreResponse:
    code = to_state.strip().upper()
    state = await state_repo.get(db, code)
    if state is None:
        raise UnknownStateError(f"Unknown or unsupported state '{code}'")

    cats: list[str] = []
    if categories:
        supported = set(supported_categories())
        cats = [c.strip().lower() for c in categories.split(",") if c.strip()]
        invalid = [c for c in cats if c not in supported]
        if invalid:
            raise ValidationError(
                f"Unsupported categories {invalid}. Choose from: {', '.join(sorted(supported))}"
            )

    radius = max(RADIUS_MIN, min(RADIUS_MAX, radius))
    target_city = (city or state.capital).strip()
    return await places_service.explore(code, state.name, target_city, cats, radius)


@router.get("/explore/categories")
async def explore_categories() -> dict[str, list[str]]:
    return {"categories": supported_categories()}
