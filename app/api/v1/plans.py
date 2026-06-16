import uuid

from fastapi import APIRouter

from app.api.v1.deps import DeviceDep, SessionDep
from app.domain.schemas.plan import (
    CreatePlanRequest,
    MovePlanResponse,
    PlanListResponse,
    TaskUpdateResponse,
    UpdateTaskRequest,
)
from app.domain.services.plan_service import plan_service

router = APIRouter()


@router.post("/plans", response_model=MovePlanResponse, status_code=201)
async def create_plan(
    body: CreatePlanRequest, db: SessionDep, device_id: DeviceDep
) -> MovePlanResponse:
    return await plan_service.create_plan(db, body, device_id)


@router.get("/plans", response_model=PlanListResponse)
async def list_plans(db: SessionDep, device_id: DeviceDep) -> PlanListResponse:
    return PlanListResponse(plans=await plan_service.list_plans(db, device_id))


@router.get("/plans/{plan_id}", response_model=MovePlanResponse)
async def get_plan(
    plan_id: uuid.UUID, db: SessionDep, device_id: DeviceDep
) -> MovePlanResponse:
    return await plan_service.get_plan(db, plan_id, device_id)


@router.patch("/plans/{plan_id}/tasks/{task_id}", response_model=TaskUpdateResponse)
async def update_task(
    plan_id: uuid.UUID,
    task_id: uuid.UUID,
    body: UpdateTaskRequest,
    db: SessionDep,
    device_id: DeviceDep,
) -> TaskUpdateResponse:
    return await plan_service.update_task(db, plan_id, task_id, body.status, device_id)
