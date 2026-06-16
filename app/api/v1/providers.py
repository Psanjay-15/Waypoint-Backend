from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter()


class ProvidersResponse(BaseModel):
    default: str
    available: list[str]


@router.get("/providers", response_model=ProvidersResponse)
async def providers() -> ProvidersResponse:
    available = settings.available_providers
    default = settings.default_llm_provider
    if default not in available and available:
        default = available[0]
    return ProvidersResponse(default=default, available=available)
