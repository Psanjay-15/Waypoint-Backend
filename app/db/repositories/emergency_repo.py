from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EmergencyContact
from app.db.repositories.base import BaseRepository


class EmergencyRepository(BaseRepository[EmergencyContact]):
    model = EmergencyContact

    async def list_for_state(
        self, db: AsyncSession, state_code: str, kind: str | None = None
    ) -> list[EmergencyContact]:
        stmt = select(EmergencyContact).where(EmergencyContact.state_code == state_code)
        if kind:
            stmt = stmt.where(EmergencyContact.kind == kind)
        stmt = stmt.order_by(EmergencyContact.kind, EmergencyContact.agency_name)
        result = await db.execute(stmt)
        return list(result.scalars())

    async def delete_for_state(self, db: AsyncSession, state_code: str) -> None:
        await db.execute(
            delete(EmergencyContact).where(EmergencyContact.state_code == state_code)
        )


emergency_repo = EmergencyRepository()
