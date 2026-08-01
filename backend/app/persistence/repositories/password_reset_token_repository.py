from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password_reset_token
from app.persistence.models import PasswordResetTokenModel


class PasswordResetTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: UUID,
        token: str,
        lifetime_minutes: int,
    ) -> PasswordResetTokenModel:
        row = PasswordResetTokenModel(
            id=uuid4(),
            user_id=user_id,
            token_hash=hash_password_reset_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=lifetime_minutes),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def consume(self, token: str, user_id: UUID) -> PasswordResetTokenModel | None:
        """Atomically mark a valid token consumed and return it once."""
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            update(PasswordResetTokenModel)
            .where(
                PasswordResetTokenModel.token_hash == hash_password_reset_token(token),
                PasswordResetTokenModel.user_id == user_id,
                PasswordResetTokenModel.consumed_at.is_(None),
                PasswordResetTokenModel.expires_at > now,
            )
            .values(consumed_at=now)
            .returning(PasswordResetTokenModel)
        )
        return result.scalar_one_or_none()
