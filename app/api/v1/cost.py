from fastapi import APIRouter

from app.domain.schemas.cost import CostRequest, CostResponse
from app.domain.services.cost_service import cost_service

router = APIRouter()


@router.post("/cost/compare", response_model=CostResponse)
async def compare_cost(body: CostRequest) -> CostResponse:
    return await cost_service.compare(body)
