"""StateShift API — application entry point (MongoDB + OpenAI)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.config import settings
from app.core.exceptions import StateShiftError
from app.core.logging import configure_logging, get_logger
from app.db import close, ping, states_col

configure_logging(settings.log_level)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("starting StateShift server")
    try:
        await ping()
        log.info("mongodb connected")
    except Exception as exc:
        log.error("mongodb connection failed: %s", exc)

    if settings.auto_seed:
        try:
            if await states_col().estimated_document_count() == 0:
                from app.scripts.ingest import ingest

                inserted = await ingest()
                log.info("auto-seeded %d states", inserted)
        except Exception as exc:
            log.warning("auto-seed skipped: %s", exc)

    log.info("server ready")
    yield
    await close()
    log.info("server shutting down")


app = FastAPI(
    title="StateShift API",
    description="Interstate relocation assistant — compare areas, live AI chat, move plans, cost.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list or ["*"],
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StateShiftError)
async def stateshift_error_handler(request: Request, exc: StateShiftError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.__class__.__name__, "detail": str(exc)},
    )


app.include_router(api_router)


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"service": "StateShift API", "docs": "/docs", "health": "/api/v1/health"}
