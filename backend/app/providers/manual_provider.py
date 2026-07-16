from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Account, Holding, Transaction
from app.persistence.repositories.account_repository import AccountRepository
from app.providers.base import FinancialDataProvider


class ManualProvider(FinancialDataProvider):
    """The default provider for user-entered accounts: there's nothing to
    "sync" — it just reads back what's already in the DB, normalized to the
    same `Account`/`Transaction`/`Holding` shapes a real integration would
    return, so callers can't tell the difference.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_accounts(self, user_id: UUID) -> list[Account]:
        return await AccountRepository(self.session).list_for_user(user_id)

    async def get_transactions(self, user_id: UUID, since: date) -> list[Transaction]:
        # TODO(Phase 2): TransactionRepository.list_for_user_since(user_id, since)
        return []

    async def get_holdings(self, user_id: UUID, account_id: UUID) -> list[Holding]:
        # TODO(Phase 2): HoldingRepository.list_for_account(account_id)
        return []
