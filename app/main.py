"""StateShift 2.0 API — application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.config import settings
from app.core.database import create_all
from app.core.exceptions import StateShiftError
from app.core.logging import configure_logging, get_logger

configure_logging(settings.log_level)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("starting StateShift server")
    await create_all()
    if settings.auto_seed:
        from app.scripts.seed_data import seed_if_empty

        await seed_if_empty()
    log.info("server ready")
    yield
    log.info("server shutting down")


app = FastAPI(
    title="StateShift 2.0 API",
    description="Interstate relocation assistant — compare states, grounded AI chat, personalized move plans.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


@app.exception_handler(StateShiftError)
async def stateshift_error_handler(
    request: Request, exc: StateShiftError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.__class__.__name__, "detail": str(exc)},
    )


app.include_router(api_router)

app.mount("/demo", StaticFiles(directory=settings.demo_dir, html=True), name="demo")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/demo")
