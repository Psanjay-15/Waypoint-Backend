from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MovePlan, PlanTask
from app.db.repositories.base import BaseRepository


class PlanRepository(BaseRepository[MovePlan]):
    model = MovePlan

    async def list_for_device(self, db: AsyncSession, device_id: str) -> list[MovePlan]:
        stmt = (
            select(MovePlan)
            .where(MovePlan.device_id == device_id)
            .order_by(MovePlan.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars())

    async def get_task(
        self, db: AsyncSession, plan_id: uuid.UUID, task_id: uuid.UUID
    ) -> PlanTask | None:
        stmt = select(PlanTask).where(
            PlanTask.id == task_id, PlanTask.plan_id == plan_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_task_status(
        self, db: AsyncSession, task: PlanTask, status: str
    ) -> PlanTask:
        task.status = status
        await db.commit()
        await db.refresh(task)
        return task


plan_repo = PlanRepository()
