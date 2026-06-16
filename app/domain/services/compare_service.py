"""Builds the corridor comparison from law facts."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DISCLAIMER
from app.core.exceptions import UnknownStateError
from app.db.repositories.law_fact_repo import law_fact_repo
from app.db.repositories.state_repo import state_repo
from app.domain.schemas.compare import (
    CompareResponse,
    ComparisonRow,
    FactOut,
    GotchasResponse,
)


class CompareService:
    async def _check_states(self, db: AsyncSession, *codes: str) -> None:
        for code in codes:
            if await state_repo.get(db, code) is None:
                raise UnknownStateError(f"Unknown or unsupported state '{code}'")

    async def compare(
        self,
        db: AsyncSession,
        from_state: str,
        to_state: str,
        category: str | None = None,
    ) -> CompareResponse:
        await self._check_states(db, from_state, to_state)
        facts = await law_fact_repo.list_for_corridor(
            db, from_state, to_state, category
        )

        rows: dict[str, ComparisonRow] = {}
        for fact in facts:
            row = rows.get(fact.comparable_key)
            if row is None:
                row = ComparisonRow(
                    comparable_key=fact.comparable_key,
                    category=fact.category,
                    title=fact.title,
                )
                rows[fact.comparable_key] = row
            out = FactOut.from_orm_fact(fact)
            if fact.state_code == from_state:
                row.from_fact = out
            else:
                row.to_fact = out
            if fact.state_code == to_state:
                row.title = fact.title

        ordered = sorted(rows.values(), key=lambda r: (r.category, r.comparable_key))
        return CompareResponse(
            from_state=from_state,
            to_state=to_state,
            category=category,
            rows=ordered,
            disclaimer=DISCLAIMER,
        )

    async def gotchas(
        self, db: AsyncSession, from_state: str, to_state: str
    ) -> GotchasResponse:
        await self._check_states(db, from_state, to_state)
        facts = await law_fact_repo.list_gotchas(db, from_state, to_state)
        return GotchasResponse(
            from_state=from_state,
            to_state=to_state,
            gotchas=[FactOut.from_orm_fact(f) for f in facts],
            disclaimer=DISCLAIMER,
        )


compare_service = CompareService()
