from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select

from app.domain.entities import PlanningProfile, User
from app.persistence.models import PlanningProfileModel, UserModel
from app.persistence.repositories.base import BaseRepository


class UserRepository(BaseRepository[UserModel]):
    model = UserModel

    async def get_by_id(self, user_id: UUID) -> User:
        row = await self._get_or_raise("User", user_id)
        return _to_domain(row)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(UserModel).where(UserModel.email == email))
        row = result.scalar_one_or_none()
        return _to_domain(row) if row else None

    async def get_hashed_password(self, email: str) -> tuple[User, str] | None:
        result = await self.session.execute(select(UserModel).where(UserModel.email == email))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _to_domain(row), row.hashed_password

    async def create(self, email: str, full_name: str, hashed_password: str) -> User:
        row = UserModel(id=uuid4(), email=email, full_name=full_name, hashed_password=hashed_password)
        self.session.add(row)
        await self.session.flush()
        # Seed a default planning profile so every user has one immediately.
        self.session.add(PlanningProfileModel(id=uuid4(), user_id=row.id))
        await self.session.flush()
        return _to_domain(row)

    async def get_planning_profile(self, user_id: UUID) -> PlanningProfile:
        result = await self.session.execute(
            select(PlanningProfileModel).where(PlanningProfileModel.user_id == user_id)
        )
        row = result.scalar_one()
        return PlanningProfile(
            user_id=row.user_id,
            target_retirement_age=row.target_retirement_age,
            target_equity_allocation=row.target_equity_allocation,
            default_withdrawal_rate=row.default_withdrawal_rate,
            include_social_security=row.include_social_security,
            expected_return=row.expected_return,
            inflation_rate=row.inflation_rate,
        )


def _to_domain(row: UserModel) -> User:
    return User(
        id=row.id,
        email=row.email,
        full_name=row.full_name,
        base_currency=row.base_currency,
        date_of_birth=row.date_of_birth,
    )
