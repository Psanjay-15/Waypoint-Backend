"""City Finder — given a state, the LLM profiles the top cities to consider."""

from __future__ import annotations

import time

from app.domain.schemas.cities import CityFinderResponse, CityFinderResult
from app.llm.factory import run_with_fallback
from app.llm.prompts import CITIES_SYSTEM, build_cities_prompt

_CACHE_TTL = 60 * 30
_cache: dict[str, tuple[float, object]] = {}


class CityFinderService:
    async def find(self, state: str, limit: int) -> CityFinderResponse:
        key = f"cities:{state}|{limit}"
        cached = _cache.get(key)
        if cached and time.time() - cached[0] < _CACHE_TTL:
            return cached[1]  # type: ignore[return-value]

        result, _ = await run_with_fallback(
            None,
            lambda p: p.structured(CITIES_SYSTEM, build_cities_prompt(state, limit), CityFinderResult),
        )

        response = CityFinderResponse(
            state=state,
            overview=result.overview,
            cities=result.cities,
            disclaimer=(
                "AI-generated city profiles — figures (cost index, rent) are approximate estimates, "
                "not exact data. Verify specifics before deciding."
            ),
        )
        _cache[key] = (time.time(), response)
        return response


city_finder_service = CityFinderService()
