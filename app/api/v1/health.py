from fastapi import APIRouter
from sqlalchemy import text

from app.api.v1.deps import SessionDep
from app.domain.schemas.common import HealthResponse
from app.vector import client as vector_client

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(db: SessionDep) -> HealthResponse:
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    if not vector_client.is_enabled():
        qdrant_status = "disabled"
    else:
        try:
            qdrant = vector_client.get_qdrant()
            await qdrant.get_collections()
            qdrant_status = "ok"
        except Exception:
            qdrant_status = "error"

    overall = "ok" if db_status == "ok" else "degraded"
    return HealthResponse(
        status=overall, db=db_status, qdrant=qdrant_status, version="0.1.0"
    )
