import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import TASK_PENDING
from app.core.database import Base


class MovePlan(Base):
    __tablename__ = "move_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    from_state: Mapped[str] = mapped_column(
        String(2), ForeignKey("states.code"), nullable=False
    )
    to_state: Mapped[str] = mapped_column(
        String(2), ForeignKey("states.code"), nullable=False
    )
    move_date: Mapped[date] = mapped_column(Date, nullable=False)
    quiz_answers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    tasks: Mapped[list["PlanTask"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PlanTask.sort_order",
    )


class PlanTask(Base):
    __tablename__ = "plan_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("move_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    deadline_offset_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TASK_PENDING
    )
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    plan: Mapped[MovePlan] = relationship(back_populates="tasks")
