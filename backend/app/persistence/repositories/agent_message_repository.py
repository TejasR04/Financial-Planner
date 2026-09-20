from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select

from app.persistence.models import AgentConversationModel, AgentMessageModel
from app.persistence.repositories.base import BaseRepository


class AgentMessageRepository(BaseRepository[AgentMessageModel]):
    model = AgentMessageModel

    async def list_for_conversation(
        self, user_id: UUID, conversation_id: UUID, limit: int = 30
    ) -> list[AgentMessageModel]:
        result = await self.session.execute(
            select(AgentMessageModel)
            .where(
                AgentMessageModel.user_id == user_id,
                AgentMessageModel.conversation_id == conversation_id,
            )
            .order_by(AgentMessageModel.created_at.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def append(
        self, user_id: UUID, conversation_id: UUID, role: str, content: str
    ) -> AgentMessageModel:
        row = AgentMessageModel(
            user_id=user_id, conversation_id=conversation_id, role=role, content=content
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def clear_all(self, user_id: UUID) -> None:
        await self.session.execute(
            delete(AgentConversationModel).where(AgentConversationModel.user_id == user_id)
        )
        await self.session.flush()

    async def prune(self, user_id: UUID, conversation_id: UUID, keep: int = 100) -> None:
        newest_ids = (
            select(AgentMessageModel.id)
            .where(
                AgentMessageModel.user_id == user_id,
                AgentMessageModel.conversation_id == conversation_id,
            )
            .order_by(AgentMessageModel.created_at.desc())
            .limit(keep)
        )
        await self.session.execute(
            delete(AgentMessageModel).where(
                AgentMessageModel.user_id == user_id,
                AgentMessageModel.conversation_id == conversation_id,
                AgentMessageModel.id.not_in(newest_ids),
            )
        )
        await self.session.flush()


class AgentConversationRepository(BaseRepository[AgentConversationModel]):
    model = AgentConversationModel

    async def create(self, user_id: UUID, title: str) -> AgentConversationModel:
        row = AgentConversationModel(user_id=user_id, title=title)
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_for_user(
        self, user_id: UUID, conversation_id: UUID
    ) -> AgentConversationModel | None:
        result = await self.session.execute(
            select(AgentConversationModel).where(
                AgentConversationModel.id == conversation_id,
                AgentConversationModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: UUID, limit: int = 50
    ) -> list[tuple[AgentConversationModel, int]]:
        result = await self.session.execute(
            select(
                AgentConversationModel,
                func.count(AgentMessageModel.id).label("message_count"),
            )
            .outerjoin(
                AgentMessageModel,
                AgentMessageModel.conversation_id == AgentConversationModel.id,
            )
            .where(AgentConversationModel.user_id == user_id)
            .group_by(AgentConversationModel.id)
            .order_by(AgentConversationModel.updated_at.desc())
            .limit(limit)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def touch(self, conversation: AgentConversationModel) -> None:
        conversation.updated_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def delete(self, conversation: AgentConversationModel) -> None:
        await self.session.delete(conversation)
        await self.session.flush()
