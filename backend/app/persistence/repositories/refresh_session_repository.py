from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_refresh_token
from app.persistence.models import RefreshSessionModel, UserModel


class RefreshSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_id: UUID, token: str, lifetime_days: int) -> RefreshSessionModel:
        row = RefreshSessionModel(
            id=uuid4(),
            user_id=user_id,
            token_hash=hash_refresh_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=lifetime_days),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def consume(self, token: str) -> RefreshSessionModel | None:
        result = await self.session.execute(
            select(RefreshSessionModel)
            .where(RefreshSessionModel.token_hash == hash_refresh_token(token))
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        now = datetime.now(timezone.utc)
        if row.revoked_at is not None:
            await self.revoke_all(row.user_id, now)
            return None
        if row.expires_at <= now:
            row.revoked_at = now
            return None
        user_active = await self.session.scalar(
            select(UserModel.id).where(UserModel.id == row.user_id, UserModel.archived_at.is_(None))
        )
        if user_active is None:
            row.revoked_at = now
            return None
        row.revoked_at = now
        return row

    async def set_replacement(self, consumed: RefreshSessionModel, replacement_id: UUID) -> None:
        consumed.replaced_by_id = replacement_id
        await self.session.flush()

    async def revoke(self, token: str) -> None:
        row = await self.session.scalar(
            select(RefreshSessionModel).where(
                RefreshSessionModel.token_hash == hash_refresh_token(token)
            )
        )
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def revoke_all(self, user_id: UUID, revoked_at: datetime | None = None) -> None:
        await self.session.execute(
            update(RefreshSessionModel)
            .where(RefreshSessionModel.user_id == user_id, RefreshSessionModel.revoked_at.is_(None))
            .values(revoked_at=revoked_at or datetime.now(timezone.utc))
        )
