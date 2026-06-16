"""Provider registry, cached construction, and fallback orchestration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import TypeVar

from app.config import settings
from app.core.exceptions import LLMError, UnsupportedProviderError
from app.core.logging import get_logger
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.grok_provider import GrokProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.perplexity_provider import PerplexityProvider

log = get_logger(__name__)

T = TypeVar("T")

_REGISTRY: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "grok": GrokProvider,
    "perplexity": PerplexityProvider,
}


@lru_cache(maxsize=8)
def get_llm_provider(name: str) -> LLMProvider:
    """Cached singleton per provider — avoids re-creating SDK clients per request."""
    if name not in _REGISTRY:
        raise UnsupportedProviderError(
            f"Unknown provider '{name}'. Supported: {', '.join(sorted(_REGISTRY))}"
        )
    if name not in settings.available_providers:
        raise UnsupportedProviderError(f"Provider '{name}' has no API key configured")
    return _REGISTRY[name]()


def _candidate_order(preferred: str | None) -> list[str]:
    order: list[str] = []
    for name in [
        preferred or settings.default_llm_provider,
        *settings.fallback_order_list,
    ]:
        if name and name not in order:
            order.append(name)
    available = [n for n in order if n in settings.available_providers]
    if not available:
        raise UnsupportedProviderError(
            "No LLM provider is configured — set at least one of OPENAI_API_KEY, "
            "ANTHROPIC_API_KEY, GEMINI_API_KEY, GROK_API_KEY in server/.env"
        )
    return available


async def run_with_fallback(
    preferred: str | None,
    call: Callable[[LLMProvider], Awaitable[T]],
) -> tuple[T, str]:
    """Try the preferred provider, then walk the fallback chain on LLM errors.

    Returns (result, provider_name_actually_used).
    """
    if preferred and preferred not in _REGISTRY:
        raise UnsupportedProviderError(
            f"Unknown provider '{preferred}'. Supported: {', '.join(sorted(_REGISTRY))}"
        )
    last_error: LLMError | None = None
    for name in _candidate_order(preferred):
        provider = get_llm_provider(name)
        try:
            result = await call(provider)
            return result, name
        except LLMError as exc:
            log.warning("provider %s failed (%s); trying next", name, exc)
            last_error = exc
    raise last_error if last_error else LLMError("all providers failed")
