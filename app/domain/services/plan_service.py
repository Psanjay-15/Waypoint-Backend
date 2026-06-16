"""Quiz → grounded LLM plan → persisted tasks with deadlines + readiness score."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DISCLAIMER, TASK_DONE
from app.core.exceptions import NotFoundError, OwnershipError
from app.db.models import MovePlan, PlanTask
from app.db.repositories.plan_repo import plan_repo
from app.domain.schemas.plan import (
    CreatePlanRequest,
    MovePlanResponse,
    MovePlanSummary,
    PlanTaskOut,
    TaskUpdateResponse,
)
from app.llm.factory import run_with_fallback

# Curated facts are no longer used to ground the plan — the LLM generates it
# directly from the corridor + quiz. (plan_repo still persists the user's plan.)
# from app.db.repositories.law_fact_repo import law_fact_repo
# from app.db.repositories.state_repo import state_repo
# from app.domain.services.retrieval_service import _to_chunk

URGENT_OFFSET_DAYS = 30


def readiness_score(tasks: list[PlanTask]) -> int:
    if not tasks:
        return 0
    total = 0
    done = 0
    for task in tasks:
        weight = 2 if task.deadline_offset_days <= URGENT_OFFSET_DAYS else 1
        total += weight
        if task.status == TASK_DONE:
            done += weight
    return round(100 * done / total)


class PlanService:
    async def create_plan(
        self, db: AsyncSession, req: CreatePlanRequest, device_id: str
    ) -> MovePlanResponse:
        generated, _provider = await run_with_fallback(
            None,
            lambda p: p.generate_plan(
                req.quiz, req.move_date, req.from_state, req.to_state, [], req.city
            ),
        )

        plan = MovePlan(
            device_id=device_id,
            from_state=req.from_state,
            to_state=req.to_state,
            move_date=req.move_date,
            quiz_answers=req.quiz.model_dump(),
        )
        ordered = sorted(generated.tasks, key=lambda t: t.deadline_offset_days)
        for i, task in enumerate(ordered):
            plan.tasks.append(
                PlanTask(
                    title=task.title,
                    description=task.description,
                    category=task.category,
                    deadline_offset_days=task.deadline_offset_days,
                    due_date=req.move_date + timedelta(days=task.deadline_offset_days),
                    source_url=None,
                    sort_order=i,
                )
            )
        plan = await plan_repo.create(db, plan)
        return self._to_response(plan)

    async def get_plan(
        self, db: AsyncSession, plan_id: uuid.UUID, device_id: str
    ) -> MovePlanResponse:
        plan = await self._owned_plan(db, plan_id, device_id)
        return self._to_response(plan)

    async def list_plans(
        self, db: AsyncSession, device_id: str
    ) -> list[MovePlanSummary]:
        plans = await plan_repo.list_for_device(db, device_id)
        return [
            MovePlanSummary(
                plan_id=p.id,
                from_state=p.from_state,
                to_state=p.to_state,
                move_date=p.move_date,
                readiness_score=readiness_score(p.tasks),
                task_count=len(p.tasks),
            )
            for p in plans
        ]

    async def update_task(
        self,
        db: AsyncSession,
        plan_id: uuid.UUID,
        task_id: uuid.UUID,
        status: str,
        device_id: str,
    ) -> TaskUpdateResponse:
        plan = await self._owned_plan(db, plan_id, device_id)
        task = await plan_repo.get_task(db, plan_id, task_id)
        if task is None:
            raise NotFoundError(f"Task '{task_id}' not found in plan '{plan_id}'")
        task = await plan_repo.update_task_status(db, task, status)
        await db.refresh(plan)
        return TaskUpdateResponse(
            task=PlanTaskOut.model_validate(task),
            readiness_score=readiness_score(plan.tasks),
        )

    async def _owned_plan(
        self, db: AsyncSession, plan_id: uuid.UUID, device_id: str
    ) -> MovePlan:
        plan = await plan_repo.get(db, plan_id)
        if plan is None:
            raise NotFoundError(f"Plan '{plan_id}' not found")
        if plan.device_id != device_id:
            raise OwnershipError("This plan belongs to a different device")
        return plan

    def _to_response(self, plan: MovePlan) -> MovePlanResponse:
        return MovePlanResponse(
            plan_id=plan.id,
            from_state=plan.from_state,
            to_state=plan.to_state,
            move_date=plan.move_date,
            readiness_score=readiness_score(plan.tasks),
            tasks=[PlanTaskOut.model_validate(t) for t in plan.tasks],
            disclaimer=DISCLAIMER,
        )


plan_service = PlanService()
