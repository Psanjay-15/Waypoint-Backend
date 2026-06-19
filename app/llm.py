"""OpenAI wrapper — the live relocation assistant.

Single responsibility: turn a user question + corridor context into a grounded
markdown answer. Swap the model via OPENAI_MODEL. Raises LLMError on any failure
so the caller can degrade gracefully.
"""

from __future__ import annotations

from openai import AsyncOpenAI

from app.config import settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger

log = get_logger(__name__)

_client: AsyncOpenAI | None = None

SYSTEM = """You are StateShift, a relocation assistant for people moving between US states.
Answer ONLY about the user's move using the CONTEXT provided.
Be concise and practical: 2-5 short sentences or a tight bullet list, in Markdown.
Ground numbers (taxes, cost index) in the CONTEXT — do not invent specific legal deadlines or dollar figures that aren't given; speak in typical ranges and tell the user to verify with the official source.
Never give legal, tax, or financial advice — this is general guidance only."""


def _get_client() -> AsyncOpenAI:
    global _client
    if not settings.has_openai:
        raise LLMError("OPENAI_API_KEY is not configured")
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def ask(question: str, context: str) -> str:
    """Return a grounded Markdown answer for the question."""
    client = _get_client()
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=600,
            temperature=0.4,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"},
            ],
        )
    except Exception as exc:  # openai raises many subtypes — normalize them
        log.warning("openai call failed: %s", exc)
        raise LLMError(f"assistant unavailable: {exc}") from exc

    answer = (resp.choices[0].message.content or "").strip()
    if not answer:
        raise LLMError("assistant returned an empty answer")
    return answer
