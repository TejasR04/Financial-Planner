from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select

from app.persistence.models import AgentMessageModel
from app.persistence.repositories.base import BaseRepository


class AgentMessageRepository(BaseRepository[AgentMessageModel]):
    model = AgentMessageModel

    async def list_for_user(self, user_id: UUID, limit: int = 30) -> list[AgentMessageModel]:
        result = await self.session.execute(
            select(AgentMessageModel)
            .where(AgentMessageModel.user_id == user_id)
            .order_by(AgentMessageModel.created_at.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def append(self, user_id: UUID, role: str, content: str) -> AgentMessageModel:
        row = AgentMessageModel(user_id=user_id, role=role, content=content)
        self.session.add(row)
        await self.session.flush()
        return row

    async def clear(self, user_id: UUID) -> None:
        await self.session.execute(
            delete(AgentMessageModel).where(AgentMessageModel.user_id == user_id)
        )
        await self.session.flush()

    async def prune(self, user_id: UUID, keep: int = 100) -> None:
        newest_ids = (
            select(AgentMessageModel.id)
            .where(AgentMessageModel.user_id == user_id)
            .order_by(AgentMessageModel.created_at.desc())
            .limit(keep)
        )
        await self.session.execute(
            delete(AgentMessageModel).where(
                AgentMessageModel.user_id == user_id,
                AgentMessageModel.id.not_in(newest_ids),
            )
        )
        await self.session.flush()
