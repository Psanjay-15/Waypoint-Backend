from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import State
from app.db.repositories.base import BaseRepository


class StateRepository(BaseRepository[State]):
    model = State

    async def list_all(self, db: AsyncSession) -> list[State]:
        result = await db.execute(select(State).order_by(State.name))
        return list(result.scalars())

    async def count(self, db: AsyncSession) -> int:
        from sqlalchemy import func

        result = await db.execute(select(func.count(State.code)))
        return int(result.scalar_one())


state_repo = StateRepository()
