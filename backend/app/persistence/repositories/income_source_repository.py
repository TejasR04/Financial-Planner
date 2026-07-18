from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select

from app.domain.entities import IncomeSource
from app.persistence.models import IncomeSourceModel
from app.persistence.repositories.base import BaseRepository


class IncomeSourceRepository(BaseRepository[IncomeSourceModel]):
    model = IncomeSourceModel

    async def list_for_user(self, user_id: UUID, active_only: bool = True) -> list[IncomeSource]:
        query = select(IncomeSourceModel).where(IncomeSourceModel.user_id == user_id)
        if active_only:
            query = query.where(IncomeSourceModel.active.is_(True))
        result = await self.session.execute(query)
        return [_to_domain(row) for row in result.scalars().all()]

    async def create(self, user_id: UUID, income_source: IncomeSource) -> IncomeSource:
        row = IncomeSourceModel(
            id=income_source.id or uuid4(),
            user_id=user_id,
            name=income_source.name,
            annual_amount=income_source.annual_amount,
            growth_rate=income_source.growth_rate,
            active=income_source.active,
        )
        self.session.add(row)
        await self.session.flush()
        return _to_domain(row)


def _to_domain(row: IncomeSourceModel) -> IncomeSource:
    return IncomeSource(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        annual_amount=row.annual_amount,
        growth_rate=row.growth_rate,
        active=row.active,
    )
