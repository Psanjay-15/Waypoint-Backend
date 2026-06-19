"""Application settings — plain class + dotenv, read once at import time."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

SERVER_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(SERVER_ROOT / ".env", override=True)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def _require(name: str) -> str:
    value = _env(name)
    if not value:
        raise RuntimeError(f"{name} is not set — add it to .env")
    return value


class Settings:
    def __init__(self) -> None:
        # MongoDB Atlas (or any mongodb:// URI).
        self.mongodb_uri: str = _require("MONGODB_URI")
        self.mongodb_db: str = _env("MONGODB_DB") or "stateshift"

        # OpenAI — powers the live assistant + cost estimates.
        self.openai_api_key: str | None = _env("OPENAI_API_KEY")
        self.openai_model: str = _env("OPENAI_MODEL") or "gpt-4o-mini"

        self.cors_origins: str = _env("CORS_ORIGINS") or ""
        self.cors_origin_regex: str | None = _env("CORS_ORIGIN_REGEX")
        self.log_level: str = _env("LOG_LEVEL") or "INFO"
        self.auto_seed: bool = _env_bool("AUTO_SEED", default=True)

        self.data_dir: Path = SERVER_ROOT / "app" / "data"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)


settings = Settings()
