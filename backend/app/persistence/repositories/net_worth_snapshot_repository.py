"""Daily observed net worth; no historical balances are inferred from current rows."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.financial_date import financial_today
from app.persistence.models import NetWorthSnapshotModel
from app.persistence.repositories.account_repository import AccountRepository


class NetWorthSnapshotRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def observe_current(self, user_id: UUID, as_of: date | None = None) -> None:
        accounts = await AccountRepository(self.session).list_for_user(user_id)
        assets = sum((account.balance for account in accounts if not account.is_liability), Decimal("0"))
        liabilities = sum((abs(account.balance) for account in accounts if account.is_liability), Decimal("0"))
        statement = insert(NetWorthSnapshotModel).values(
            id=uuid4(), user_id=user_id, as_of=as_of or financial_today(),
            assets=assets, liabilities=liabilities,
        )
        await self.session.execute(statement.on_conflict_do_update(
            constraint="uq_net_worth_snapshots_user_date",
            set_={"assets": statement.excluded.assets, "liabilities": statement.excluded.liabilities},
        ))

    async def history_for_user(self, user_id: UUID) -> list[tuple[date, Decimal, Decimal]]:
        result = await self.session.execute(
            select(NetWorthSnapshotModel.as_of, NetWorthSnapshotModel.assets, NetWorthSnapshotModel.liabilities)
            .where(NetWorthSnapshotModel.user_id == user_id)
            .order_by(NetWorthSnapshotModel.as_of)
        )
        return [(as_of, Decimal(assets), Decimal(liabilities)) for as_of, assets, liabilities in result.all()]
