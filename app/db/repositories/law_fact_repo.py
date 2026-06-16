from __future__ import annotations

import uuid

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LawFact
from app.db.repositories.base import BaseRepository


class LawFactRepository(BaseRepository[LawFact]):
    model = LawFact

    async def list_for_corridor(
        self,
        db: AsyncSession,
        from_state: str,
        to_state: str,
        category: str | None = None,
    ) -> list[LawFact]:
        stmt = select(LawFact).where(LawFact.state_code.in_([from_state, to_state]))
        if category:
            stmt = stmt.where(LawFact.category == category)
        stmt = stmt.order_by(
            LawFact.category, LawFact.comparable_key, LawFact.state_code
        )
        result = await db.execute(stmt)
        return list(result.scalars())

    async def list_for_state(self, db: AsyncSession, state_code: str) -> list[LawFact]:
        stmt = select(LawFact).where(LawFact.state_code == state_code)
        result = await db.execute(stmt)
        return list(result.scalars())

    async def list_gotchas(
        self, db: AsyncSession, from_state: str, to_state: str
    ) -> list[LawFact]:
        stmt = (
            select(LawFact)
            .where(
                LawFact.state_code.in_([from_state, to_state]),
                LawFact.is_gotcha.is_(True),
            )
            .order_by(LawFact.state_code, LawFact.category)
        )
        result = await db.execute(stmt)
        return list(result.scalars())

    async def get_many(self, db: AsyncSession, ids: list[uuid.UUID]) -> list[LawFact]:
        if not ids:
            return []
        result = await db.execute(select(LawFact).where(LawFact.id.in_(ids)))
        return list(result.scalars())

    async def list_all(self, db: AsyncSession) -> list[LawFact]:
        result = await db.execute(select(LawFact))
        return list(result.scalars())

    async def category_summaries(self, db: AsyncSession, state_code: str) -> list[dict]:
        stmt = (
            select(
                LawFact.category,
                func.count(LawFact.id).label("fact_count"),
                func.sum(case((LawFact.is_gotcha.is_(True), 1), else_=0)).label(
                    "gotcha_count"
                ),
            )
            .where(LawFact.state_code == state_code)
            .group_by(LawFact.category)
            .order_by(LawFact.category)
        )
        result = await db.execute(stmt)
        return [
            {
                "category": row.category,
                "fact_count": row.fact_count,
                "gotcha_count": int(row.gotcha_count or 0),
            }
            for row in result
        ]

    async def delete_for_state(self, db: AsyncSession, state_code: str) -> None:
        await db.execute(delete(LawFact).where(LawFact.state_code == state_code))


law_fact_repo = LawFactRepository()
