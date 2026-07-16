"""PlaidProvider — Phase 6 in the roadmap (ARCHITECTURE.md §12).

Stubbed here to lock in the interface: nothing outside this file should
ever import a Plaid SDK type. When implemented, methods will call the Plaid
`/accounts/get`, `/transactions/sync`, and `/investments/holdings/get`
endpoints and map their response shapes to `Account`/`Transaction`/`Holding`.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from app.core.exceptions import ProviderError
from app.domain.entities import Account, Holding, Transaction
from app.providers.base import FinancialDataProvider


class PlaidProvider(FinancialDataProvider):
    def __init__(self, client_id: str | None, secret: str | None, environment: str = "sandbox"):
        self.client_id = client_id
        self.secret = secret
        self.environment = environment

    async def get_accounts(self, user_id: UUID) -> list[Account]:
        raise ProviderError("PlaidProvider is not yet implemented (see ARCHITECTURE.md Phase 6)")

    async def get_transactions(self, user_id: UUID, since: date) -> list[Transaction]:
        raise ProviderError("PlaidProvider is not yet implemented (see ARCHITECTURE.md Phase 6)")

    async def get_holdings(self, user_id: UUID, account_id: UUID) -> list[Holding]:
        raise ProviderError("PlaidProvider is not yet implemented (see ARCHITECTURE.md Phase 6)")
