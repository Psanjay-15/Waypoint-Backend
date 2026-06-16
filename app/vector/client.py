"""Qdrant client singleton — None when semantic search is disabled."""

from __future__ import annotations

from qdrant_client import AsyncQdrantClient

from app.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_client: AsyncQdrantClient | None = None


def get_qdrant() -> AsyncQdrantClient | None:
    global _client
    if not settings.qdrant_url:
        return None
    if _client is None:
        _client = AsyncQdrantClient(url=settings.qdrant_url)
        log.info("qdrant client created (%s)", settings.qdrant_url)
    return _client


def is_enabled() -> bool:
    return bool(settings.qdrant_url)
