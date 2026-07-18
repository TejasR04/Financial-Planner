from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select

from app.domain.entities import Goal
from app.domain.enums import GoalStatus
from app.persistence.models import GoalModel
from app.persistence.repositories.base import BaseRepository


class GoalRepository(BaseRepository[GoalModel]):
    model = GoalModel

    async def list_for_user(self, user_id: UUID) -> list[Goal]:
        result = await self.session.execute(
            select(GoalModel).where(GoalModel.user_id == user_id).order_by(GoalModel.priority, GoalModel.target_date)
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def get_by_id(self, goal_id: UUID) -> Goal:
        row = await self._get_or_raise("Goal", goal_id)
        return _to_domain(row)

    async def create(self, user_id: UUID, goal: Goal) -> Goal:
        row = GoalModel(
            id=goal.id or uuid4(),
            user_id=user_id,
            title=goal.title,
            target_amount=goal.target_amount,
            target_date=goal.target_date,
            target_age=goal.target_age,
            priority=goal.priority,
            status=goal.status.value,
            linked_account_id=goal.linked_account_id,
        )
        self.session.add(row)
        await self.session.flush()
        return _to_domain(row)

    async def update(self, goal_id: UUID, **fields) -> Goal:
        row = await self._get_or_raise("Goal", goal_id)
        for key, value in fields.items():
            if value is None:
                continue
            if key == "status" and isinstance(value, GoalStatus):
                value = value.value
            setattr(row, key, value)
        await self.session.flush()
        return _to_domain(row)

    async def delete(self, goal_id: UUID) -> None:
        row = await self._get_or_raise("Goal", goal_id)
        await self.session.delete(row)
        await self.session.flush()


def _to_domain(row: GoalModel) -> Goal:
    return Goal(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        target_amount=row.target_amount,
        target_date=row.target_date,
        target_age=row.target_age,
        priority=row.priority,
        status=GoalStatus(row.status),
        linked_account_id=row.linked_account_id,
    )
