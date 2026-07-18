from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import User
from app.persistence.repositories.financial_health_repository import FinancialHealthScoreRepository
from app.persistence.repositories.insight_repository import InsightRepository
from app.persistence.snapshot_builder import build_financial_snapshot
from app.schemas.insight import InsightResponse
from app.services.financial_health_service import FinancialHealthScore
from app.services.insight_service import InsightService

router = APIRouter(prefix="/insights", tags=["insights"])

insight_service = InsightService()


@router.get("", response_model=list[InsightResponse])
async def list_insights(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[InsightResponse]:
    existing = await InsightRepository(db).list_for_user(current_user.id, limit=20)
    if existing:
        return [InsightResponse.model_validate(i, from_attributes=True) for i in existing]

    # No insights generated yet for this user: derive them now from the
    # latest health score (or a fresh one if none exists) rather than
    # returning an empty feed on a user's first visit.
    snapshot = await build_financial_snapshot(db, current_user.id)
    health_repo = FinancialHealthScoreRepository(db)
    latest_score_row = await health_repo.get_latest(current_user.id)
    if latest_score_row is None:
        return []
    score = FinancialHealthScore(
        overall=latest_score_row.overall,
        liquidity=latest_score_row.liquidity,
        diversification=latest_score_row.diversification,
        debt_ratio=latest_score_row.debt_ratio,
        savings_discipline=latest_score_row.savings_discipline,
    )
    drafts = insight_service.generate(snapshot, score)
    created = await InsightRepository(db).save_drafts(current_user.id, drafts)
    await db.commit()
    return [InsightResponse.model_validate(i, from_attributes=True) for i in created]
