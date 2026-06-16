"""Safety rating + rent comparison + (LLM) city-fit.

Crime and rent come from curated, cited datasets (FBI UCR + Census ACS) shipped
in the repo — no external API, no key, no card. The city-fit narrative is a
best-effort LLM summary grounded in those real numbers (degrades to null).
"""

from __future__ import annotations

import json

from app.config import settings
from app.core.exceptions import LLMError, UnknownStateError
from app.core.logging import get_logger
from app.domain.schemas.livability import (
    CityRent,
    LivabilityResponse,
    SafetyScore,
)
from app.llm.factory import run_with_fallback
from app.llm.prompts import build_city_fit_prompt

log = get_logger(__name__)

VIOLENT_WEIGHT = 5


def _load() -> dict:
    from app.config import SERVER_ROOT

    try:
        return json.loads((SERVER_ROOT / "app" / "data" / "livability.json").read_text())
    except FileNotFoundError:
        log.warning("livability.json missing — safety endpoint will report unsupported states")
        return {}


_DATA = _load()
_NATIONAL = _DATA.get("_national", {"violent_per_100k": 380, "property_per_100k": 1916})
_PROFILES = {k: v for k, v in _DATA.items() if not k.startswith("_")}
_REF_INDEX = (
    _NATIONAL["violent_per_100k"] * VIOLENT_WEIGHT + _NATIONAL["property_per_100k"]
)


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


def _safety_score(state_code: str) -> SafetyScore:
    p = _PROFILES[state_code]
    s = p["safety"]
    index = s["violent_per_100k"] * VIOLENT_WEIGHT + s["property_per_100k"]
    score = max(0, min(100, round(100 - (index / _REF_INDEX) * 50)))
    pct = round((index / _REF_INDEX - 1) * 100)
    if pct > 2:
        vs = f"{pct}% above the national crime level"
    elif pct < -2:
        vs = f"{abs(pct)}% below the national crime level"
    else:
        vs = "about the national crime level"
    return SafetyScore(
        state_code=state_code,
        state_name=p["name"],
        violent_per_100k=s["violent_per_100k"],
        property_per_100k=s["property_per_100k"],
        score=score,
        grade=_grade(score),
        vs_national=vs,
        source=s["source"],
        source_url=s["source_url"],
        year=s["year"],
    )


class LivabilityService:
    def supported(self, code: str) -> bool:
        return code in _PROFILES

    async def assess(self, from_state: str, to_state: str) -> LivabilityResponse:
        for code in (from_state, to_state):
            if code not in _PROFILES:
                raise UnknownStateError(f"No livability data for state '{code}'")

        from_safety = _safety_score(from_state)
        to_safety = _safety_score(to_state)

        dest = _PROFILES[to_state]
        cities = sorted(dest["cities"], key=lambda c: c["median_rent"])
        city_rents = [CityRent(**c) for c in cities]

        fit, fit_available = await self._city_fit(to_safety, cities)

        return LivabilityResponse(
            from_safety=from_safety,
            to_safety=to_safety,
            safer_move=to_safety.score >= from_safety.score,
            rent_state=to_state,
            rent_source=dest["rent_source"],
            rent_source_url=dest["rent_source_url"],
            city_rents=city_rents,
            fit=fit,
            fit_available=fit_available,
            disclaimer=(
                "Crime figures are FBI UCR 2023 and rents are Census ACS 2023 — the most recent "
                "complete official data (both are published with a ~1-year lag, so there is no "
                "newer dataset yet). Approximate; verify against the linked sources. The 'best for' "
                "read is an AI summary, not a guarantee."
            ),
        )

    async def _city_fit(self, to_safety: SafetyScore, cities: list[dict]):
        if not settings.available_providers or not cities:
            return None, False
        prompt = build_city_fit_prompt(
            to_safety.state_name,
            {
                "violent_per_100k": to_safety.violent_per_100k,
                "property_per_100k": to_safety.property_per_100k,
                "score": to_safety.score,
                "grade": to_safety.grade,
            },
            cities[0],
            cities[-1],
        )
        try:
            fit, _ = await run_with_fallback(None, lambda p: p.assess_city(prompt))
            return fit, True
        except LLMError as exc:
            log.warning("city-fit LLM failed: %s", exc)
            return None, False


livability_service = LivabilityService()
