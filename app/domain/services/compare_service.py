"""Corridor comparison — data fetched live from the LLM (DB path commented out)."""

from __future__ import annotations

import time
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DISCLAIMER
from app.domain.schemas.compare import (
    CompareResponse,
    ComparisonRow,
    FactOut,
    GotchasResponse,
    LlmCompareResult,
)
from app.llm.factory import run_with_fallback
from app.llm.prompts import COMPARE_SYSTEM, build_compare_prompt

# --- DB-backed imports (kept for reference; comparison now uses the LLM) ---
# from app.core.exceptions import UnknownStateError
# from app.db.repositories.law_fact_repo import law_fact_repo
# from app.db.repositories.state_repo import state_repo

_CACHE_TTL = 60 * 30
_cache: dict[str, tuple[float, object]] = {}

LLM_DISCLAIMER = "AI-generated from public sources — verify each via its linked official source. " + DISCLAIMER


def _fact_out(state_code: str, category: str, title: str, fact, is_gotcha: bool) -> FactOut:
    return FactOut(
        id=f"{state_code}:{category}:{title}".lower().replace(" ", "_"),
        state_code=state_code,
        category=category,
        title=title,
        summary=fact.summary,
        is_gotcha=is_gotcha,
        source_url=fact.source_url,
        source_name=fact.source_name,
        last_verified=date.today(),
    )


class CompareService:
    async def _rows(self, from_state: str, to_state: str, category: str | None) -> list[ComparisonRow]:
        key = f"cmp:{from_state}|{to_state}|{category or 'all'}"
        cached = _cache.get(key)
        if cached and time.time() - cached[0] < _CACHE_TTL:
            return cached[1]  # type: ignore[return-value]

        result, _ = await run_with_fallback(
            None,
            lambda p: p.structured(
                COMPARE_SYSTEM, build_compare_prompt(from_state, to_state, category), LlmCompareResult
            ),
        )
        rows = [
            ComparisonRow(
                comparable_key=r.comparable_key,
                category=r.category,
                title=r.title,
                from_fact=_fact_out(from_state, r.category, r.title, r.from_fact, r.is_gotcha),
                to_fact=_fact_out(to_state, r.category, r.title, r.to_fact, r.is_gotcha),
            )
            for r in result.rows
        ]
        _cache[key] = (time.time(), rows)
        return rows

    async def compare(
        self,
        db: AsyncSession,
        from_state: str,
        to_state: str,
        category: str | None = None,
    ) -> CompareResponse:
        rows = await self._rows(from_state, to_state, category)
        return CompareResponse(
            from_state=from_state,
            to_state=to_state,
            category=category,
            rows=rows,
            disclaimer=LLM_DISCLAIMER,
        )

    async def gotchas(
        self, db: AsyncSession, from_state: str, to_state: str
    ) -> GotchasResponse:
        rows = await self._rows(from_state, to_state, None)
        gotchas = [r.to_fact for r in rows if r.to_fact and r.to_fact.is_gotcha]
        return GotchasResponse(
            from_state=from_state,
            to_state=to_state,
            gotchas=gotchas,
            disclaimer=LLM_DISCLAIMER,
        )


compare_service = CompareService()
