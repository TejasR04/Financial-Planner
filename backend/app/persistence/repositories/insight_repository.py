from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select

from app.domain.entities import Insight
from app.domain.enums import InsightKind
from app.persistence.models import InsightModel
from app.persistence.repositories.base import BaseRepository
from app.services.insight_service import InsightDraft


class InsightRepository(BaseRepository[InsightModel]):
    model = InsightModel

    async def list_for_user(self, user_id: UUID, limit: int = 20) -> list[Insight]:
        result = await self.session.execute(
            select(InsightModel)
            .where(InsightModel.user_id == user_id)
            .order_by(InsightModel.generated_at.desc())
            .limit(limit)
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def save_drafts(self, user_id: UUID, drafts: list[InsightDraft]) -> list[Insight]:
        rows = [
            InsightModel(id=uuid4(), user_id=user_id, kind=d.kind.value, text=d.text, meta=d.meta)
            for d in drafts
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return [_to_domain(row) for row in rows]


def _to_domain(row: InsightModel) -> Insight:
    return Insight(
        id=row.id, user_id=row.user_id, kind=InsightKind(row.kind), text=row.text, meta=row.meta,
        generated_at=row.generated_at,
    )
