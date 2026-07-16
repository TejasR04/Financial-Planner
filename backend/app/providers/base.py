"""FinancialDataProvider — nothing outside app/providers/ should import a
provider-specific SDK type. Every provider returns the same normalized
domain objects regardless of source.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from app.domain.entities import Account, Holding, Transaction


class FinancialDataProvider(ABC):
    @abstractmethod
    async def get_accounts(self, user_id: UUID) -> list[Account]:
        ...

    @abstractmethod
    async def get_transactions(self, user_id: UUID, since: date) -> list[Transaction]:
        ...

    @abstractmethod
    async def get_holdings(self, user_id: UUID, account_id: UUID) -> list[Holding]:
        ...
