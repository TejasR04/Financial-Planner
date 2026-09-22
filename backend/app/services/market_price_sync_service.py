from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.repositories.account_repository import AccountRepository
from app.persistence.repositories.holding_repository import HoldingRepository
from app.persistence.repositories.investment_value_snapshot_repository import InvestmentValueSnapshotRepository
from app.providers.market_data_provider import TiingoMarketDataProvider

CENT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class MarketSyncResult:
    symbols_updated: int
    holdings_updated: int
    accounts_updated: int
    errors: dict[str, str]


class MarketPriceSyncService:
    def __init__(self, session: AsyncSession, provider: TiingoMarketDataProvider):
        self._accounts = AccountRepository(session)
        self._holdings = HoldingRepository(session)
        self._history = InvestmentValueSnapshotRepository(session)
        self._provider = provider

    async def sync_user(self, user_id: UUID) -> MarketSyncResult:
        holdings = await self._holdings.list_automatic_for_user(user_id)
        if not holdings:
            return MarketSyncResult(0, 0, 0, {})

        batch = await self._provider.latest_prices({holding.symbol for holding in holdings})
        account_deltas: dict[UUID, Decimal] = {}
        holdings_updated = 0
        for holding in holdings:
            price = batch.prices.get(holding.symbol.strip().upper())
            if price is None or price.as_of < holding.as_of:
                continue
            new_value = (holding.quantity * price.price).quantize(CENT, rounding=ROUND_HALF_UP)
            account_deltas[holding.account_id] = account_deltas.get(holding.account_id, Decimal("0")) + (
                new_value - holding.market_value
            )
            await self._holdings.apply_market_price_for_user(user_id, holding.id, price.price, price.as_of)
            holdings_updated += 1

        updated_accounts = []
        for account_id, delta in account_deltas.items():
            updated_accounts.append(await self._accounts.adjust_manual_balance(user_id, account_id, delta))
        await self._history.record_for_accounts(updated_accounts)
        return MarketSyncResult(
            symbols_updated=len(batch.prices),
            holdings_updated=holdings_updated,
            accounts_updated=len(updated_accounts),
            errors=batch.errors,
        )
