from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select

from app.domain.entities import Liability
from app.core.exceptions import NotFoundError
from app.persistence.models import AccountModel, LiabilityModel
from app.persistence.repositories.base import BaseRepository


class LiabilityRepository(BaseRepository[LiabilityModel]):
    model = LiabilityModel

    async def list_for_user(self, user_id: UUID) -> list[Liability]:
        result = await self.session.execute(
            select(LiabilityModel)
            .join(AccountModel, AccountModel.id == LiabilityModel.account_id)
            .where(
                AccountModel.user_id == user_id,
                AccountModel.archived_at.is_(None),
            )
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def get_for_account(self, account_id: UUID) -> Liability | None:
        result = await self.session.execute(select(LiabilityModel).where(LiabilityModel.account_id == account_id))
        row = result.scalar_one_or_none()
        return _to_domain(row) if row else None

    async def create(self, liability: Liability) -> Liability:
        row = LiabilityModel(
            id=liability.id or uuid4(),
            account_id=liability.account_id,
            principal=liability.principal,
            interest_rate=liability.interest_rate,
            term_months=liability.term_months,
            minimum_payment=liability.minimum_payment,
            origination_date=liability.origination_date,
        )
        self.session.add(row)
        await self.session.flush()
        return _to_domain(row)

    async def get_for_user_account(self, user_id: UUID, account_id: UUID) -> Liability | None:
        row = await self.session.scalar(select(LiabilityModel).join(AccountModel).where(LiabilityModel.account_id == account_id, AccountModel.user_id == user_id, AccountModel.archived_at.is_(None)))
        return _to_domain(row) if row else None

    async def upsert_for_user_account(self, user_id: UUID, account_id: UUID, **fields) -> Liability:
        account = await self.session.scalar(select(AccountModel).where(AccountModel.id == account_id, AccountModel.user_id == user_id, AccountModel.archived_at.is_(None)))
        if account is None:
            raise NotFoundError("Account", str(account_id))
        row = await self.session.scalar(select(LiabilityModel).where(LiabilityModel.account_id == account_id))
        if row is None:
            row = LiabilityModel(id=uuid4(), account_id=account_id, **fields)
            self.session.add(row)
        else:
            for key, value in fields.items():
                setattr(row, key, value)
        await self.session.flush()
        return _to_domain(row)

    async def delete_for_user_account(self, user_id: UUID, account_id: UUID) -> None:
        row = await self.session.scalar(select(LiabilityModel).join(AccountModel).where(LiabilityModel.account_id == account_id, AccountModel.user_id == user_id))
        if row is None:
            raise NotFoundError("Liability details", str(account_id))
        await self.session.delete(row)
        await self.session.flush()


def _to_domain(row: LiabilityModel) -> Liability:
    return Liability(
        id=row.id,
        account_id=row.account_id,
        principal=row.principal,
        interest_rate=row.interest_rate,
        term_months=row.term_months,
        minimum_payment=row.minimum_payment,
        origination_date=row.origination_date,
    )
