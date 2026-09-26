from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.domain.entities import Account
from app.domain.enums import AccountType
from app.persistence.models import AccountModel, HoldingValueSnapshotModel, InvestmentValueSnapshotModel
from app.persistence.repositories.base import BaseRepository


class InvestmentValueSnapshotRepository(BaseRepository[InvestmentValueSnapshotModel]):
    model = InvestmentValueSnapshotModel

    async def record_holding_values(self, account_ids: list[UUID], holdings, as_of: date | None = None) -> None:
        """Snapshot observed position values, preserving same-day updates and zeroing closed positions."""
        if not account_ids:
            return
        snapshot_date = as_of or date.today()
        result = await self.session.execute(select(HoldingValueSnapshotModel).where(
            HoldingValueSnapshotModel.account_id.in_(account_ids),
            HoldingValueSnapshotModel.as_of == snapshot_date,
        ))
        existing = {(row.account_id, row.symbol): row for row in result.scalars().all()}
        latest_prior = (
            select(
                HoldingValueSnapshotModel.account_id.label("account_id"),
                HoldingValueSnapshotModel.symbol.label("symbol"),
                func.max(HoldingValueSnapshotModel.as_of).label("latest_as_of"),
            )
            .where(
                HoldingValueSnapshotModel.account_id.in_(account_ids),
                HoldingValueSnapshotModel.as_of < snapshot_date,
            )
            .group_by(HoldingValueSnapshotModel.account_id, HoldingValueSnapshotModel.symbol)
            .subquery()
        )
        prior_result = await self.session.execute(
            select(HoldingValueSnapshotModel.account_id, HoldingValueSnapshotModel.symbol)
            .join(
                latest_prior,
                (HoldingValueSnapshotModel.account_id == latest_prior.c.account_id)
                & (HoldingValueSnapshotModel.symbol == latest_prior.c.symbol)
                & (HoldingValueSnapshotModel.as_of == latest_prior.c.latest_as_of),
            )
            .where(HoldingValueSnapshotModel.value != Decimal("0"))
        )
        prior_keys = set(prior_result.all())
        totals: dict[tuple[UUID, str], Decimal] = {}
        for holding in holdings:
            if holding.account_id not in account_ids:
                continue
            key = (holding.account_id, holding.symbol.strip().upper())
            totals[key] = totals.get(key, Decimal("0")) + holding.market_value
        # A refreshed account is a complete observation: positions whose
        # latest prior observation is nonzero but absent now have a real zero.
        # Already closed positions do not get repeated zero rows on every sync.
        for key in prior_keys:
            totals.setdefault(key, Decimal("0"))
        # Mark a position closed when it disappears from the latest observed account holdings.
        for key, row in existing.items():
            row.value = totals.pop(key, Decimal("0"))
        for (account_id, symbol), value in totals.items():
            self.session.add(HoldingValueSnapshotModel(
                id=uuid4(), account_id=account_id, symbol=symbol, as_of=snapshot_date, value=value
            ))
        await self.session.flush()

    async def holding_history_for_user(self, user_id: UUID, account_id: UUID, symbol: str) -> list[tuple[date, Decimal]]:
        result = await self.session.execute(
            select(HoldingValueSnapshotModel.as_of, HoldingValueSnapshotModel.value)
            .join(AccountModel, AccountModel.id == HoldingValueSnapshotModel.account_id)
            .where(AccountModel.user_id == user_id, AccountModel.archived_at.is_(None),
                   HoldingValueSnapshotModel.account_id == account_id,
                   HoldingValueSnapshotModel.symbol == symbol.strip().upper())
            .order_by(HoldingValueSnapshotModel.as_of)
        )
        return [(as_of, Decimal(value)) for as_of, value in result.all()]

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
            select(
                InvestmentValueSnapshotModel.account_id,
                InvestmentValueSnapshotModel.as_of,
                InvestmentValueSnapshotModel.value,
            )
            .join(AccountModel, AccountModel.id == InvestmentValueSnapshotModel.account_id)
            .where(
                AccountModel.user_id == user_id,
                AccountModel.archived_at.is_(None),
                AccountModel.type.in_((AccountType.INVESTMENT.value, AccountType.RETIREMENT.value)),
            )
            .order_by(InvestmentValueSnapshotModel.as_of, InvestmentValueSnapshotModel.account_id)
        )
        latest_values: dict[UUID, Decimal] = {}
        totals: list[tuple[date, Decimal]] = []
        current_date: date | None = None
        for account_id, as_of, value in result.all():
            if current_date is not None and as_of != current_date:
                totals.append((current_date, sum(latest_values.values(), Decimal("0"))))
            latest_values[account_id] = Decimal(value)
            current_date = as_of
        if current_date is not None:
            totals.append((current_date, sum(latest_values.values(), Decimal("0"))))
        return totals
