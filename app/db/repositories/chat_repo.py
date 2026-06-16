from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatLog
from app.db.repositories.base import BaseRepository


class ChatRepository(BaseRepository[ChatLog]):
    model = ChatLog

    async def find_cached(self, db: AsyncSession, question_hash: str) -> ChatLog | None:

        stmt = (
            select(ChatLog)
            .where(ChatLog.question_hash == question_hash, ChatLog.confident.is_(True))
            .order_by(ChatLog.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


chat_repo = ChatRepository()
