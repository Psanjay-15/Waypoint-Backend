"""Text embeddings via the OpenAI embeddings API."""

from __future__ import annotations

from openai import AsyncOpenAI

from app.config import settings
from app.core.exceptions import RetrievalError

_client: AsyncOpenAI | None = None

EMBEDDING_DIM = 1536


def _get_client() -> AsyncOpenAI:
    global _client
    if not settings.openai_api_key:
        raise RetrievalError("embeddings unavailable: OPENAI_API_KEY not set")
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = _get_client()
    try:
        resp = await client.embeddings.create(
            model=settings.embedding_model, input=texts
        )
    except Exception as exc:
        raise RetrievalError(f"embedding call failed: {exc}") from exc
    return [item.embedding for item in resp.data]
