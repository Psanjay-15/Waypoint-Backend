"""Generic repository — all SQL lives in this layer."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    async def get(self, db: AsyncSession, id_: Any) -> ModelT | None:
        return await db.get(self.model, id_)

    async def create(self, db: AsyncSession, obj: ModelT) -> ModelT:
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def update(self, db: AsyncSession, id_: Any, **fields: Any) -> ModelT | None:
        obj = await db.get(self.model, id_)
        if obj is None:
            return None
        for key, value in fields.items():
            setattr(obj, key, value)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def delete(self, db: AsyncSession, id_: Any) -> bool:
        obj = await db.get(self.model, id_)
        if obj is None:
            return False
        await db.delete(obj)
        await db.commit()
        return True
