"""Generic async repository base. Concrete repositories translate between
ORM rows (app.persistence.models) and domain entities (app.domain.entities)
so services never see a SQLAlchemy row.
"""
from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_or_raise(self, entity_name: str, id_: UUID) -> ModelT:
        row = await self.session.get(self.model, id_)
        if row is None:
            raise NotFoundError(entity_name, str(id_))
        return row
