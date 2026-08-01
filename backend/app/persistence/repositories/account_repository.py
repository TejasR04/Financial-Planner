from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select, update

from app.core.exceptions import ValidationError
from app.domain.entities import Account
from app.domain.enums import AccountStatus, AccountType
from app.persistence.models import AccountModel
from app.persistence.repositories.base import BaseRepository


class AccountRepository(BaseRepository[AccountModel]):
    model = AccountModel

    async def list_for_user(self, user_id: UUID, type_: AccountType | None = None) -> list[Account]:
        query = select(AccountModel).where(
            AccountModel.user_id == user_id,
            AccountModel.archived_at.is_(None),
        )
        if type_ is not None:
            query = query.where(AccountModel.type == type_.value)
        result = await self.session.execute(query.order_by(AccountModel.name))
        return [_to_domain(row) for row in result.scalars().all()]

    async def get_by_id(self, account_id: UUID) -> Account:
        row = await self._get_or_raise("Account", account_id)
        return _to_domain(row)

    async def get_for_user(self, user_id: UUID, account_id: UUID) -> Account:
        result = await self.session.execute(
            select(AccountModel).where(
                AccountModel.id == account_id,
                AccountModel.user_id == user_id,
                AccountModel.archived_at.is_(None),
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("Account", str(account_id))
        return _to_domain(row)

    async def create(self, user_id: UUID, account: Account) -> Account:
        balance = -account.balance if account.is_liability and account.balance > 0 else account.balance
        row = AccountModel(
            id=account.id or uuid4(),
            user_id=user_id,
            institution_id=account.institution_id,
            name=account.name,
            type=account.type.value,
            mask=account.mask,
            currency=account.currency,
            balance=balance,
            apy=account.apy,
            status=account.status.value,
            external_account_id=account.external_account_id,
        )
        self.session.add(row)
        await self.session.flush()
        return _to_domain(row)

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
            existing.archived_at = None
            # A successful Plaid read is meaningful even when the balance is
            # unchanged. The UI uses updated_at as its last-sync timestamp,
            # so force a write rather than relying on SQLAlchemy dirty
            # checking to notice a balance change.
            existing.updated_at = datetime.now(timezone.utc)
            await self.session.flush()
            return _to_domain(existing)

        return await self.create(user_id, account)

    async def update_manual_for_user(self, user_id: UUID, account_id: UUID, **fields) -> Account:
        row = await self._row_for_user(user_id, account_id)
        if row.institution_id is not None:
            raise ValidationError("Linked accounts are updated by their institution; only manual accounts can be edited.")
        for field, value in fields.items():
            if (
                field == "balance"
                and value is not None
                and row.type in {AccountType.CREDIT.value, AccountType.LOAN.value}
                and value > 0
            ):
                value = -value
            setattr(row, field, value)
        await self.session.flush()
        return _to_domain(row)

    async def archive_for_user(self, user_id: UUID, account_id: UUID) -> None:
        row = await self._row_for_user(user_id, account_id)
        row.archived_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def archive_missing_from_plaid(
        self, user_id: UUID, institution_id: UUID, external_account_ids: list[str]
    ) -> None:
        query = update(AccountModel).where(
            AccountModel.user_id == user_id,
            AccountModel.institution_id == institution_id,
            AccountModel.archived_at.is_(None),
            AccountModel.external_account_id.is_not(None),
        )
        if external_account_ids:
            query = query.where(AccountModel.external_account_id.not_in(external_account_ids))
        await self.session.execute(query.values(archived_at=datetime.now(timezone.utc)))
        await self.session.flush()

    async def archive_and_detach_institution(self, user_id: UUID, institution_id: UUID) -> None:
        # Detach archived rows too. Plaid can archive an account before the
        # user unlinks its institution, and leaving that FK in place prevents
        # the institution row from being deleted.
        await self.session.execute(
            update(AccountModel)
            .where(
                AccountModel.user_id == user_id,
                AccountModel.institution_id == institution_id,
            )
            .values(
                archived_at=func.coalesce(AccountModel.archived_at, datetime.now(timezone.utc)),
                institution_id=None,
            )
        )
        await self.session.flush()

    async def count_active_for_institutions(self, user_id: UUID) -> dict[UUID, int]:
        from sqlalchemy import func

        result = await self.session.execute(
            select(AccountModel.institution_id, func.count())
            .where(
                AccountModel.user_id == user_id,
                AccountModel.institution_id.is_not(None),
                AccountModel.archived_at.is_(None),
            )
            .group_by(AccountModel.institution_id)
        )
        return {institution_id: count for institution_id, count in result.all()}

    async def _row_for_user(self, user_id: UUID, account_id: UUID) -> AccountModel:
        result = await self.session.execute(
            select(AccountModel).where(
                AccountModel.id == account_id,
                AccountModel.user_id == user_id,
                AccountModel.archived_at.is_(None),
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("Account", str(account_id))
        return row


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
        archived_at=row.archived_at,
    )
