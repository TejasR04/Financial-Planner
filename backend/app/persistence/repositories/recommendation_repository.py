from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import delete, select

from app.core.exceptions import NotFoundError
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
        """Refresh actionable rows without resurrecting a user's decisions.

        A rule's title and category form its stable identity. Existing new rows
        keep their IDs while their estimates are refreshed; applied or
        dismissed rows suppress the same rule on later generations.
        """
        result = await self.session.execute(
            select(RecommendationModel).where(RecommendationModel.user_id == user_id)
        )
        existing = result.scalars().all()
        decided_keys = {
            _draft_key(row.title, row.category)
            for row in existing
            if row.status != RecommendationStatus.NEW.value
        }
        new_by_key = {
            _draft_key(row.title, row.category): row
            for row in existing
            if row.status == RecommendationStatus.NEW.value
        }

        rows: list[RecommendationModel] = []
        active_keys: set[tuple[str, str]] = set()
        for draft in drafts:
            key = _draft_key(draft.title, draft.category)
            if key in decided_keys or key in active_keys:
                continue
            active_keys.add(key)
            row = new_by_key.get(key)
            if row is None:
                row = RecommendationModel(
                    id=uuid4(),
                    user_id=user_id,
                    title=draft.title,
                    body=draft.body,
                    category=draft.category,
                    impact_value=draft.impact_value,
                    effort=draft.effort.value,
                    confidence=draft.confidence,
                    status=RecommendationStatus.NEW.value,
                )
                self.session.add(row)
            else:
                row.body = draft.body
                row.impact_value = draft.impact_value
                row.effort = draft.effort.value
                row.confidence = draft.confidence
            rows.append(row)

        stale_ids = [row.id for key, row in new_by_key.items() if key not in active_keys]
        if stale_ids:
            await self.session.execute(
                delete(RecommendationModel).where(
                    RecommendationModel.user_id == user_id,
                    RecommendationModel.id.in_(stale_ids),
                )
            )
        await self.session.flush()
        return [_to_domain(row) for row in rows]

    async def set_status_for_user(
        self,
        user_id: UUID,
        recommendation_id: UUID,
        status: RecommendationStatus,
    ) -> Recommendation:
        result = await self.session.execute(
            select(RecommendationModel).where(
                RecommendationModel.id == recommendation_id,
                RecommendationModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("Recommendation", str(recommendation_id))
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


def _draft_key(title: str, category: str) -> tuple[str, str]:
    return (title.strip().casefold(), category.strip().casefold())
