from fastapi import APIRouter

from app.config import settings
from app.db import ping

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    try:
        await ping()
        db = "ok"
    except Exception:
        db = "error"
    return {
        "status": "ok" if db == "ok" else "degraded",
        "db": db,
        "openai": settings.has_openai,
        "version": "0.2.0",
    }
