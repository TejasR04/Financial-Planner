from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import UserModel
from app.persistence.reporting_models import AgentTokenModel


class AgentTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        user_id: UUID,
        name: str,
        token_hash: str,
        token_prefix: str,
        expires_at: datetime,
    ) -> AgentTokenModel:
        row = AgentTokenModel(
            id=uuid4(),
            user_id=user_id,
            name=name,
            token_hash=token_hash,
            token_prefix=token_prefix,
            scopes=["reports:read"],
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_for_user(self, user_id: UUID) -> list[AgentTokenModel]:
        result = await self.session.execute(
            select(AgentTokenModel)
            .where(AgentTokenModel.user_id == user_id)
            .order_by(AgentTokenModel.created_at.desc(), AgentTokenModel.id.desc())
        )
        return list(result.scalars().all())

    async def revoke_for_user(self, user_id: UUID, token_id: UUID) -> AgentTokenModel | None:
        row = await self.session.scalar(
            select(AgentTokenModel).where(
                AgentTokenModel.id == token_id,
                AgentTokenModel.user_id == user_id,
            )
        )
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(timezone.utc)
            await self.session.flush()
        return row

    async def get_active_for_hash(self, token_hash: str) -> AgentTokenModel | None:
        now = datetime.now(timezone.utc)
        return await self.session.scalar(
            select(AgentTokenModel)
            .join(UserModel, UserModel.id == AgentTokenModel.user_id)
            .where(
                AgentTokenModel.token_hash == token_hash,
                AgentTokenModel.revoked_at.is_(None),
                AgentTokenModel.expires_at > now,
                UserModel.archived_at.is_(None),
            )
        )
