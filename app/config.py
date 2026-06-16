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


def _env_bool(name: str) -> bool:
    raw = _env(name)
    return raw is not None and raw.lower() in ("1", "true", "yes", "on")


def _require(name: str) -> str:
    value = _env(name)
    if not value:
        raise RuntimeError(f"{name} is not set — copy .env.example to .env and fill it in")
    return value


class Settings:
    def __init__(self) -> None:
        self.database_url: str = _require("DATABASE_URL")

        self.openai_api_key: str | None = _env("OPENAI_API_KEY")
        self.anthropic_api_key: str | None = _env("ANTHROPIC_API_KEY")
        self.gemini_api_key: str | None = _env("GEMINI_API_KEY")
        self.grok_api_key: str | None = _env("GROK_API_KEY")
        self.grok_base_url: str | None = _env("GROK_BASE_URL")
        self.perplexity_api_key: str | None = _env("PERPLEXITY_API_KEY")
        self.perplexity_base_url: str = _env("PERPLEXITY_BASE_URL") or "https://api.perplexity.ai"
        self.perplexity_model: str = _env("PERPLEXITY_MODEL") or "sonar"

        self.default_llm_provider: str | None = _env("DEFAULT_LLM_PROVIDER")
        self.llm_fallback_order: str = _env("LLM_FALLBACK_ORDER") or ""

        self.qdrant_url: str | None = _env("QDRANT_URL")
        self.embedding_model: str | None = _env("EMBEDDING_MODEL")

        self.cors_origins: str = _env("CORS_ORIGINS") or ""
        self.cors_origin_regex: str | None = _env("CORS_ORIGIN_REGEX")
        self.log_level: str = _env("LOG_LEVEL") or "INFO"
        self.auto_seed: bool = _env_bool("AUTO_SEED")

        self.data_dir: Path = Path(
            _env("DATA_DIR") or str(SERVER_ROOT / "app" / "data" / "states")
        )
        self.demo_dir: Path = SERVER_ROOT / "app" / "static" / "demo"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def fallback_order_list(self) -> list[str]:
        return [
            p.strip().lower() for p in self.llm_fallback_order.split(",") if p.strip()
        ]

    @property
    def available_providers(self) -> list[str]:
        keys = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "gemini": self.gemini_api_key,
            "grok": self.grok_api_key,
            "perplexity": self.perplexity_api_key,
        }
        return [name for name, key in keys.items() if key]


settings = Settings()
