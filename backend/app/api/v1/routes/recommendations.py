from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import User
from app.domain.enums import RecommendationStatus
from app.persistence.repositories.recommendation_repository import RecommendationRepository
from app.persistence.snapshot_builder import build_financial_snapshot
from app.schemas.recommendation import RecommendationResponse, RecommendationUpdateRequest
from app.services.recommendation_engine import RecommendationEngine

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

recommendation_engine = RecommendationEngine()


@router.get("", response_model=list[RecommendationResponse])
async def list_recommendations(
    status: RecommendationStatus | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RecommendationResponse]:
    rows = await RecommendationRepository(db).list_for_user(current_user.id, status)
    return [RecommendationResponse.model_validate(r, from_attributes=True) for r in rows]


@router.post("/generate", response_model=list[RecommendationResponse])
async def generate_recommendations(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[RecommendationResponse]:
    """Assembles the user's current FinancialSnapshot, runs
    `RecommendationEngine` (pure, no DB access) against it, and persists the
    resulting drafts as new `status=new` recommendations.
    """
    snapshot = await build_financial_snapshot(db, current_user.id)
    drafts = recommendation_engine.generate(snapshot)
    created = await RecommendationRepository(db).save_drafts(current_user.id, drafts)
    await db.commit()
    return [RecommendationResponse.model_validate(r, from_attributes=True) for r in created]


@router.patch("/{recommendation_id}", response_model=RecommendationResponse)
async def update_recommendation(
    recommendation_id: UUID,
    body: RecommendationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecommendationResponse:
    updated = await RecommendationRepository(db).set_status(recommendation_id, body.status)
    await db.commit()
    return RecommendationResponse.model_validate(updated, from_attributes=True)
