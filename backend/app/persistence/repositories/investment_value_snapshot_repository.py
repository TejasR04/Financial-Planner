from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.domain.entities import Account
from app.domain.enums import AccountType
from app.persistence.models import AccountModel, InvestmentValueSnapshotModel
from app.persistence.repositories.base import BaseRepository


class InvestmentValueSnapshotRepository(BaseRepository[InvestmentValueSnapshotModel]):
    model = InvestmentValueSnapshotModel

    async def record_for_accounts(self, accounts: list[Account], as_of: date | None = None) -> None:
        """Store the latest value once per account per calendar day.

        A same-day sync replaces the preliminary value, leaving the chart with
        one clear closing value rather than a noisy series of refreshes.
        """
        snapshot_date = as_of or date.today()
        eligible_accounts = [
            account
            for account in accounts
            if account.type in {AccountType.INVESTMENT, AccountType.RETIREMENT}
        ]
        if not eligible_accounts:
            return

        result = await self.session.execute(
            select(InvestmentValueSnapshotModel).where(
                InvestmentValueSnapshotModel.account_id.in_(
                    [account.id for account in eligible_accounts]
                ),
                InvestmentValueSnapshotModel.as_of == snapshot_date,
            )
        )
        existing_by_account_id = {
            row.account_id: row for row in result.scalars().all()
        }
        for account in eligible_accounts:
            row = existing_by_account_id.get(account.id)
            if row is None:
                self.session.add(
                    InvestmentValueSnapshotModel(
                        id=uuid4(), account_id=account.id, as_of=snapshot_date, value=account.balance
                    )
                )
            else:
                row.value = account.balance
        await self.session.flush()

    async def daily_totals_for_user(self, user_id: UUID) -> list[tuple[date, Decimal]]:
        result = await self.session.execute(
            select(InvestmentValueSnapshotModel.as_of, func.sum(InvestmentValueSnapshotModel.value))
            .join(AccountModel, AccountModel.id == InvestmentValueSnapshotModel.account_id)
            .where(AccountModel.user_id == user_id, AccountModel.archived_at.is_(None))
            .group_by(InvestmentValueSnapshotModel.as_of)
            .order_by(InvestmentValueSnapshotModel.as_of)
        )
        return [(as_of, Decimal(value)) for as_of, value in result.all()]
