import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LawFact(Base):
    __tablename__ = "law_facts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    state_code: Mapped[str] = mapped_column(
        String(2), ForeignKey("states.code"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(64), nullable=False)
    comparable_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_structured: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    is_gotcha: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_verified: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_law_facts_state_category", "state_code", "category"),)
