from fastapi import APIRouter, Query

from app.core.exceptions import ValidationError
from app.domain.schemas.cities import CityFinderResponse
from app.domain.services.city_finder_service import city_finder_service

router = APIRouter()


@router.get("/cities", response_model=CityFinderResponse)
async def cities(
    state: str = Query(..., description="State code, e.g. TX"),
    limit: int = Query(10, ge=3, le=15, description="How many cities to profile"),
) -> CityFinderResponse:
    code = state.strip().upper()
    if len(code) != 2 or not code.isalpha():
        raise ValidationError("state must be a 2-letter code, e.g. 'TX'")
    return await city_finder_service.find(code, limit)
