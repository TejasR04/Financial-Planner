from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select

from app.domain.entities import Recommendation
from app.domain.enums import RecommendationEffort, RecommendationStatus
from app.persistence.models import RecommendationModel
from app.persistence.repositories.base import BaseRepository
from app.services.recommendation_engine import RecommendationDraft


class RecommendationRepository(BaseRepository[RecommendationModel]):
    model = RecommendationModel

    async def list_for_user(self, user_id: UUID, status: RecommendationStatus | None = None) -> list[Recommendation]:
        query = select(RecommendationModel).where(RecommendationModel.user_id == user_id)
        if status is not None:
            query = query.where(RecommendationModel.status == status.value)
        query = query.order_by(RecommendationModel.impact_value.desc())
        result = await self.session.execute(query)
        return [_to_domain(row) for row in result.scalars().all()]

    async def save_drafts(self, user_id: UUID, drafts: list[RecommendationDraft]) -> list[Recommendation]:
        """Persists freshly generated drafts as new `new`-status rows. This
        v1 does not dedupe against existing open recommendations — running
        `/recommendations/generate` twice will produce two rows for the same
        underlying opportunity. See ARCHITECTURE.md's Phase 4 follow-up note
        for the dedup key this should use once product defines "same
        recommendation" (likely category + rounded impact_value).
        """
        rows = [
            RecommendationModel(
                id=uuid4(),
                user_id=user_id,
                title=d.title,
                body=d.body,
                category=d.category,
                impact_value=d.impact_value,
                effort=d.effort.value,
                confidence=d.confidence,
                status=RecommendationStatus.NEW.value,
            )
            for d in drafts
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return [_to_domain(row) for row in rows]

    async def set_status(self, recommendation_id: UUID, status: RecommendationStatus) -> Recommendation:
        row = await self._get_or_raise("Recommendation", recommendation_id)
        row.status = status.value
        await self.session.flush()
        return _to_domain(row)


def _to_domain(row: RecommendationModel) -> Recommendation:
    return Recommendation(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        body=row.body,
        category=row.category,
        impact_value=row.impact_value,
        effort=RecommendationEffort(row.effort),
        confidence=float(row.confidence),
        status=RecommendationStatus(row.status),
        generated_at=row.generated_at,
    )
