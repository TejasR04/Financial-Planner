from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select

from app.persistence.models import FinancialHealthScoreModel
from app.persistence.repositories.base import BaseRepository
from app.services.financial_health_service import FinancialHealthScore


class FinancialHealthScoreRepository(BaseRepository[FinancialHealthScoreModel]):
    model = FinancialHealthScoreModel

    async def get_latest(self, user_id: UUID) -> FinancialHealthScoreModel | None:
        result = await self.session.execute(
            select(FinancialHealthScoreModel)
            .where(FinancialHealthScoreModel.user_id == user_id)
            .order_by(FinancialHealthScoreModel.calculated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def save(self, user_id: UUID, score: FinancialHealthScore) -> FinancialHealthScoreModel:
        row = FinancialHealthScoreModel(
            id=uuid4(),
            user_id=user_id,
            overall=score.overall,
            liquidity=score.liquidity,
            diversification=score.diversification,
            debt_ratio=score.debt_ratio,
            savings_discipline=score.savings_discipline,
        )
        self.session.add(row)
        await self.session.flush()
        return row
