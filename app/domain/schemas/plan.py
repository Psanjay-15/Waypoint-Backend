from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.schemas.chat import _normalize_state


class QuizAnswers(BaseModel):
    has_job_lined_up: bool = False
    owns_vehicle: bool = False
    has_kids: bool = False
    has_pets: bool = False
    licensed_profession: str | None = Field(
        None, max_length=64, description="e.g. 'nurse', 'teacher'"
    )
    housing: Literal["rent", "own"] = "rent"
    owns_business: bool = False
    registered_voter: bool = False


class CreatePlanRequest(BaseModel):
    from_state: str
    to_state: str
    move_date: date
    city: str | None = Field(
        None, max_length=120, description="Destination city; flavors task wording"
    )
    quiz: QuizAnswers = QuizAnswers()

    _norm_from = field_validator("from_state", mode="before")(_normalize_state)
    _norm_to = field_validator("to_state", mode="before")(_normalize_state)


class GeneratedTask(BaseModel):
    """Structured output target for plan generation (one task)."""

    title: str = Field(..., max_length=200)
    description: str = Field("", max_length=1000)
    category: str = Field(
        ..., description="taxes|driving|housing|healthcare|education|legal|logistics"
    )
    deadline_offset_days: int = Field(
        ...,
        ge=-120,
        le=180,
        description="Days relative to move date; negative = before the move.",
    )
    fact_id: str | None = Field(
        None, description="fact_id of the provided fact justifying this task, if any."
    )


class GeneratedPlan(BaseModel):
    """Structured output target for all LLM providers (plan generation)."""

    tasks: list[GeneratedTask] = Field(..., min_length=5, max_length=25)


class PlanTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    category: str
    deadline_offset_days: int
    due_date: date
    status: str
    source_url: str | None = None
    sort_order: int


class MovePlanResponse(BaseModel):
    plan_id: uuid.UUID
    from_state: str
    to_state: str
    move_date: date
    readiness_score: int
    tasks: list[PlanTaskOut]
    disclaimer: str


class MovePlanSummary(BaseModel):
    plan_id: uuid.UUID
    from_state: str
    to_state: str
    move_date: date
    readiness_score: int
    task_count: int


class PlanListResponse(BaseModel):
    plans: list[MovePlanSummary]


class UpdateTaskRequest(BaseModel):
    status: Literal["pending", "done", "skipped"]


class TaskUpdateResponse(BaseModel):
    task: PlanTaskOut
    readiness_score: int
