import asyncio
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from app.domain.entities import Account, Holding
from app.domain.enums import AccountType, AssetClass
from app.providers.market_data_provider import MarketPrice, MarketPriceBatch, TiingoMarketDataProvider
from app.services import market_price_sync_service as module


@pytest.mark.asyncio
async def test_missing_api_key_retains_prices_and_reports_each_symbol():
    result = await TiingoMarketDataProvider(None).latest_prices({"VOO", "VTI"})
    assert result.prices == {}
    assert set(result.errors) == {"VOO", "VTI"}


@pytest.mark.asyncio
async def test_tiingo_fetches_distinct_symbols_concurrently():
    active_requests = 0
    max_active_requests = 0

    async def respond(_request):
        nonlocal active_requests, max_active_requests
        active_requests += 1
        max_active_requests = max(max_active_requests, active_requests)
        await asyncio.sleep(0.01)
        active_requests -= 1
        return httpx.Response(200, json=[{"date": "2026-09-25T00:00:00Z", "close": 100}])

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        result = await TiingoMarketDataProvider("test-key", client).latest_prices({"VOO", "VTI", "VXUS"})
    finally:
        await client.aclose()

    assert set(result.prices) == {"VOO", "VTI", "VXUS"}
    assert max_active_requests == 3


@pytest.mark.asyncio
async def test_market_sync_applies_holding_change_as_account_delta(monkeypatch):
    user_id = uuid4()
    account_id = uuid4()
    holding = Holding(
        id=uuid4(), account_id=account_id, symbol="VOO", quantity=Decimal("10"),
        cost_basis=Decimal("4000"), market_value=Decimal("5000"),
        asset_class=AssetClass.EQUITY, as_of=date(2026, 9, 20), pricing_mode="automatic",
    )
    updated_account = Account(
        id=account_id, user_id=user_id, name="Brokerage", type=AccountType.INVESTMENT,
        balance=Decimal("10100"),
    )
    holdings = SimpleNamespace(
        list_automatic_for_user=AsyncMock(return_value=[holding]),
        list_for_user=AsyncMock(return_value=[holding]),
        apply_market_price_for_user=AsyncMock(return_value=holding),
    )
    accounts = SimpleNamespace(adjust_manual_balance=AsyncMock(return_value=updated_account))
    history = SimpleNamespace(record_for_accounts=AsyncMock())
    history.record_holding_values = AsyncMock()
    monkeypatch.setattr(module, "HoldingRepository", lambda _: holdings)
    monkeypatch.setattr(module, "AccountRepository", lambda _: accounts)
    monkeypatch.setattr(module, "InvestmentValueSnapshotRepository", lambda _: history)
    provider = SimpleNamespace(latest_prices=AsyncMock(return_value=MarketPriceBatch(
        prices={"VOO": MarketPrice("VOO", Decimal("510"), date(2026, 9, 21))}, errors={}
    )))

    result = await module.MarketPriceSyncService(SimpleNamespace(), provider).sync_user(user_id)

    accounts.adjust_manual_balance.assert_awaited_once_with(user_id, account_id, Decimal("100.00"))
    holdings.apply_market_price_for_user.assert_awaited_once_with(
        user_id, holding.id, Decimal("510"), date(2026, 9, 21)
    )
    history.record_for_accounts.assert_awaited_once_with([updated_account])
    history.record_holding_values.assert_awaited_once_with([account_id], [holding])
    assert result.holdings_updated == 1
    assert result.accounts_updated == 1


@pytest.mark.asyncio
async def test_market_sync_does_not_replace_a_newer_manual_value(monkeypatch):
    user_id = uuid4()
    holding = Holding(
        id=uuid4(), account_id=uuid4(), symbol="VOO", quantity=Decimal("10"),
        cost_basis=Decimal("4000"), market_value=Decimal("5000"),
        asset_class=AssetClass.EQUITY, as_of=date(2026, 9, 21), pricing_mode="automatic",
    )
    holdings = SimpleNamespace(
        list_automatic_for_user=AsyncMock(return_value=[holding]),
        apply_market_price_for_user=AsyncMock(),
    )
    accounts = SimpleNamespace(adjust_manual_balance=AsyncMock())
    history = SimpleNamespace(record_for_accounts=AsyncMock())
    monkeypatch.setattr(module, "HoldingRepository", lambda _: holdings)
    monkeypatch.setattr(module, "AccountRepository", lambda _: accounts)
    monkeypatch.setattr(module, "InvestmentValueSnapshotRepository", lambda _: history)
    provider = SimpleNamespace(latest_prices=AsyncMock(return_value=MarketPriceBatch(
        prices={"VOO": MarketPrice("VOO", Decimal("490"), date(2026, 9, 20))}, errors={}
    )))

    result = await module.MarketPriceSyncService(SimpleNamespace(), provider).sync_user(user_id)

    holdings.apply_market_price_for_user.assert_not_awaited()
    accounts.adjust_manual_balance.assert_not_awaited()
    assert result.holdings_updated == 0
