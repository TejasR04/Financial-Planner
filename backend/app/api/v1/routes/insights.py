from datetime import datetime, timezone
from uuid import uuid5

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import User
from app.persistence.activity_history import load_budget_activity_summary
from app.persistence.repositories.insight_repository import InsightRepository
from app.persistence.snapshot_builder import build_financial_snapshot
from app.schemas.insight import InsightResponse
from app.services.insight_service import InsightService

router = APIRouter(prefix="/insights", tags=["insights"])

insight_service = InsightService()


@router.get("", response_model=list[InsightResponse])
async def list_insights(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[InsightResponse]:
    snapshot = await build_financial_snapshot(db, current_user.id)
    history, monthly_cash_flow = await load_budget_activity_summary(db, current_user.id)
    drafts = insight_service.generate(snapshot, history, monthly_cash_flow)
    return [InsightResponse(id=uuid5(current_user.id, draft.meta), kind=draft.kind, text=draft.text,
                            meta=draft.meta, generated_at=datetime.now(timezone.utc)) for draft in drafts]


@router.post("/generate", response_model=list[InsightResponse])
async def generate_insights(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[InsightResponse]:
    """Generate a new insight set only when the user explicitly requests analysis."""
    snapshot = await build_financial_snapshot(db, current_user.id)
    history, monthly_cash_flow = await load_budget_activity_summary(db, current_user.id)
    drafts = insight_service.generate(snapshot, history, monthly_cash_flow)
    created = await InsightRepository(db).save_drafts(current_user.id, drafts)
    await db.commit()
    return [InsightResponse.model_validate(i, from_attributes=True) for i in created]
