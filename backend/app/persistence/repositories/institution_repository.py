from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.persistence.models import InstitutionModel
from app.persistence.repositories.base import BaseRepository


class InstitutionRepository(BaseRepository[InstitutionModel]):
    model = InstitutionModel

    async def name_map_for_user(self, user_id: UUID) -> dict[UUID, str]:
        """Return {institution_id: name} for every institution owned by the
        user. Used to enrich AccountResponse with a human-readable
        institution name without adding a persistence concern to the
        Account domain entity.
        """
        query = select(InstitutionModel.id, InstitutionModel.name).where(
            InstitutionModel.user_id == user_id
        )
        result = await self.session.execute(query)
        return {row.id: row.name for row in result.all()}
