"""Safety + rent + city-fit — fetched live from the LLM.

The previous curated implementation (livability.json crime/rent) is kept in git
history; the data file remains in place but is no longer read. Crime/rent
figures here are AI-reported and approximate — verify against the linked source.
"""

from __future__ import annotations

import time

from app.domain.schemas.livability import (
    CityFit,
    LivabilityResponse,
    LlmSafetyResult,
    SafetyScore,
)
from app.llm.factory import run_with_fallback
from app.llm.prompts import SAFETY_DIRECT_SYSTEM, build_safety_prompt

VIOLENT_WEIGHT = 5
_NATIONAL_VIOLENT = 364
_NATIONAL_PROPERTY = 1916
_REF_INDEX = _NATIONAL_VIOLENT * VIOLENT_WEIGHT + _NATIONAL_PROPERTY

_CACHE_TTL = 60 * 30
_cache: dict[str, tuple[float, object]] = {}


def _grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _safety_score(s) -> SafetyScore:
    index = s.violent_per_100k * VIOLENT_WEIGHT + s.property_per_100k
    score = max(0, min(100, round(100 - (index / _REF_INDEX) * 50)))
    pct = round((index / _REF_INDEX - 1) * 100)
    if pct > 2:
        vs = f"{pct}% above the national crime level"
    elif pct < -2:
        vs = f"{abs(pct)}% below the national crime level"
    else:
        vs = "about the national crime level"
    return SafetyScore(
        state_code=s.state_code,
        state_name=s.state_name,
        violent_per_100k=s.violent_per_100k,
        property_per_100k=s.property_per_100k,
        score=score,
        grade=_grade(score),
        vs_national=vs,
        source=s.source,
        source_url=s.source_url,
        year=s.year,
    )


class LivabilityService:
    def supported(self, code: str) -> bool:
        # LLM mode works for any state; validation no longer depends on the DB.
        return len(code) == 2 and code.isalpha()

    async def assess(self, from_state: str, to_state: str) -> LivabilityResponse:
        key = f"safety:{from_state}|{to_state}"
        cached = _cache.get(key)
        if cached and time.time() - cached[0] < _CACHE_TTL:
            return cached[1]  # type: ignore[return-value]

        result, _ = await run_with_fallback(
            None,
            lambda p: p.structured(
                SAFETY_DIRECT_SYSTEM, build_safety_prompt(from_state, to_state), LlmSafetyResult
            ),
        )

        from_safety = _safety_score(result.from_safety)
        to_safety = _safety_score(result.to_safety)

        response = LivabilityResponse(
            from_safety=from_safety,
            to_safety=to_safety,
            safer_move=to_safety.score >= from_safety.score,
            rent_state=to_state,
            rent_source=result.rent_source,
            rent_source_url=result.rent_source_url,
            city_rents=sorted(result.city_rents, key=lambda c: c.median_rent),
            fit=CityFit(summary=result.fit_summary, best_for=result.fit_best_for),
            fit_available=True,
            disclaimer=(
                "AI-reported crime and rent figures — approximate, verify against the linked "
                "sources. Crime/rent data is published with a lag. The 'best for' read is an AI "
                "summary, not a guarantee."
            ),
        )
        _cache[key] = (time.time(), response)
        return response


livability_service = LivabilityService()
