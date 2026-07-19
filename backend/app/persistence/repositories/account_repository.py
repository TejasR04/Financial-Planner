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
            external_account_id=account.external_account_id,
        )
        self.session.add(row)
        await self.session.flush()
        return _to_domain(row)

    async def get_by_external_account_id(self, external_account_id: str) -> Account | None:
        query = select(AccountModel).where(AccountModel.external_account_id == external_account_id)
        result = await self.session.execute(query)
        row = result.scalar_one_or_none()
        return _to_domain(row) if row is not None else None

    async def upsert_from_plaid(self, user_id: UUID, account: Account) -> Account:
        """Create or update an account sourced from Plaid, matched by
        `external_account_id`. Ownership is always the authenticated
        `user_id` passed in by the caller — never trusted from the Plaid
        payload itself.
        """
        existing = None
        if account.external_account_id is not None:
            query = select(AccountModel).where(
                AccountModel.external_account_id == account.external_account_id,
                AccountModel.user_id == user_id,
            )
            result = await self.session.execute(query)
            existing = result.scalar_one_or_none()

        if existing is not None:
            existing.name = account.name
            existing.type = account.type.value
            existing.mask = account.mask
            existing.currency = account.currency
            existing.balance = account.balance
            existing.status = account.status.value
            existing.institution_id = account.institution_id
            await self.session.flush()
            return _to_domain(existing)

        return await self.create(user_id, account)

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
        external_account_id=row.external_account_id,
    )
