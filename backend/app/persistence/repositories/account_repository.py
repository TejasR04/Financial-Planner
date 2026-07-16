from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select

from app.domain.entities import Account
from app.domain.enums import AccountStatus, AccountType
from app.persistence.models import AccountModel
from app.persistence.repositories.base import BaseRepository


class AccountRepository(BaseRepository[AccountModel]):
    model = AccountModel

    async def list_for_user(self, user_id: UUID, type_: AccountType | None = None) -> list[Account]:
        query = select(AccountModel).where(AccountModel.user_id == user_id)
        if type_ is not None:
            query = query.where(AccountModel.type == type_.value)
        result = await self.session.execute(query.order_by(AccountModel.name))
        return [_to_domain(row) for row in result.scalars().all()]

    async def get_by_id(self, account_id: UUID) -> Account:
        row = await self._get_or_raise("Account", account_id)
        return _to_domain(row)

    async def create(self, user_id: UUID, account: Account) -> Account:
        row = AccountModel(
            id=account.id or uuid4(),
            user_id=user_id,
            institution_id=account.institution_id,
            name=account.name,
            type=account.type.value,
            mask=account.mask,
            currency=account.currency,
            balance=account.balance,
            apy=account.apy,
            status=account.status.value,
        )
        self.session.add(row)
        await self.session.flush()
        return _to_domain(row)

    async def update_balance(self, account_id: UUID, new_balance) -> Account:
        row = await self._get_or_raise("Account", account_id)
        row.balance = new_balance
        await self.session.flush()
        return _to_domain(row)

    async def delete(self, account_id: UUID) -> None:
        row = await self._get_or_raise("Account", account_id)
        await self.session.delete(row)
        await self.session.flush()


def _to_domain(row: AccountModel) -> Account:
    return Account(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        type=AccountType(row.type),
        balance=row.balance,
        currency=row.currency,
        institution_id=row.institution_id,
        mask=row.mask,
        apy=row.apy,
        status=AccountStatus(row.status),
        updated_at=row.updated_at,
    )
