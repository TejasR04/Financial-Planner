import asyncio
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.dialects import postgresql

from app.domain.entities import Account, Holding
from app.domain.enums import AccountType, AssetClass
from app.api.v1.routes import sync as sync_routes
from app.persistence.repositories.holding_repository import HoldingRepository
from app.providers.market_data_provider import MarketPrice, MarketPriceBatch, TiingoMarketDataProvider
from app.services import market_price_sync_service as module


@pytest.mark.asyncio
async def test_automatic_holding_query_is_limited_to_active_manual_accounts():
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [])
    )))

    assert await HoldingRepository(session).list_automatic_for_user(uuid4()) == []

    sql = str(session.execute.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "accounts.user_id" in sql
    assert "accounts.archived_at IS NULL" in sql
    assert "accounts.institution_id IS NULL" in sql
    assert "holdings.pricing_mode =" in sql


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("symbol", "VTI"),
    ("market_value", Decimal("5500")),
    ("as_of", date(2026, 9, 22)),
])
async def test_manual_holding_edits_clear_stored_quote(field, value, monkeypatch):
    account_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(), account_id=account_id, symbol="VOO", quantity=Decimal("10"),
        cost_basis=Decimal("4000"), market_value=Decimal("5000"), asset_class="equity",
        as_of=date(2026, 9, 21), pricing_mode="automatic", last_price=Decimal("500"),
    )
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=row),
        get=AsyncMock(return_value=SimpleNamespace(institution_id=None)),
        flush=AsyncMock(),
    )

    updated = await HoldingRepository(session).update_for_user(uuid4(), row.id, **{field: value})

    assert updated.last_price is None
    assert getattr(updated, field) == value


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
async def test_tiingo_uses_latest_close_and_normalizes_symbols():
    requests = []

    async def respond(request):
        requests.append(request)
        return httpx.Response(200, json=[
            {"date": "2026-09-24T00:00:00Z", "close": "499.25"},
            {"date": "2026-09-25T00:00:00Z", "close": "501.75"},
        ])

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        result = await TiingoMarketDataProvider("test-key", client).latest_prices({" voo "})
    finally:
        await client.aclose()

    assert result.prices["VOO"] == MarketPrice("VOO", Decimal("501.75"), date(2026, 9, 25))
    assert requests[0].url.path.endswith("/VOO/prices")
    assert requests[0].headers["Authorization"] == "Token test-key"


@pytest.mark.asyncio
async def test_tiingo_reports_non_finite_close_as_unavailable():
    async def respond(_request):
        return httpx.Response(200, json=[{"date": "2026-09-25T00:00:00Z", "close": "Infinity"}])

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        result = await TiingoMarketDataProvider("test-key", client).latest_prices({"VOO"})
    finally:
        await client.aclose()

    assert result.prices == {}
    assert result.errors == {"VOO": "No current market price was available."}


@pytest.mark.asyncio
async def test_manual_refresh_route_passes_configured_tiingo_provider(monkeypatch):
    user_id = uuid4()
    api_key = "unit-test-key"
    db = SimpleNamespace(commit=AsyncMock())
    provider = object()
    market_result = SimpleNamespace(
        symbols_updated=1, holdings_updated=1, accounts_updated=1, errors={}
    )
    market_sync = AsyncMock(return_value=market_result)
    monkeypatch.setattr(sync_routes, "get_settings", lambda: SimpleNamespace(
        plaid_client_id=None, plaid_secret=None, tiingo_api_key=api_key
    ))
    monkeypatch.setattr(sync_routes, "LoanBalanceAutomationService", lambda _: SimpleNamespace(
        apply=AsyncMock(return_value=0)
    ))
    monkeypatch.setattr(sync_routes, "InvestmentContributionService", lambda _: SimpleNamespace(
        apply=AsyncMock(return_value=0)
    ))
    monkeypatch.setattr(sync_routes, "TiingoMarketDataProvider", lambda key: provider if key == api_key else None)
    monkeypatch.setattr(sync_routes, "MarketPriceSyncService", lambda session, market_provider: (
        SimpleNamespace(sync_user=market_sync)
        if session is db and market_provider is provider else None
    ))

    response = await sync_routes.refresh_financial_data(SimpleNamespace(id=user_id), db)

    market_sync.assert_awaited_once_with(user_id)
    db.commit.assert_awaited_once()
    assert response.market.holdings_updated == 1
    assert response.market.errors == {}


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
async def test_market_sync_accepts_first_close_before_manual_as_of_date(monkeypatch):
    user_id = uuid4()
    holding = Holding(
        id=uuid4(), account_id=uuid4(), symbol="VOO", quantity=Decimal("10"),
        cost_basis=Decimal("4000"), market_value=Decimal("5000"),
        asset_class=AssetClass.EQUITY, as_of=date(2026, 9, 21), pricing_mode="automatic",
        last_price=None,
    )
    holdings = SimpleNamespace(
        list_automatic_for_user=AsyncMock(return_value=[holding]),
        list_for_user=AsyncMock(return_value=[holding]),
        apply_market_price_for_user=AsyncMock(),
    )
    accounts = SimpleNamespace(adjust_manual_balance=AsyncMock())
    history = SimpleNamespace(
        record_for_accounts=AsyncMock(), record_holding_values=AsyncMock()
    )
    monkeypatch.setattr(module, "HoldingRepository", lambda _: holdings)
    monkeypatch.setattr(module, "AccountRepository", lambda _: accounts)
    monkeypatch.setattr(module, "InvestmentValueSnapshotRepository", lambda _: history)
    provider = SimpleNamespace(latest_prices=AsyncMock(return_value=MarketPriceBatch(
        prices={"VOO": MarketPrice("VOO", Decimal("490"), date(2026, 9, 20))}, errors={}
    )))

    result = await module.MarketPriceSyncService(SimpleNamespace(), provider).sync_user(user_id)

    holdings.apply_market_price_for_user.assert_awaited_once_with(
        user_id, holding.id, Decimal("490"), date(2026, 9, 20)
    )
    accounts.adjust_manual_balance.assert_awaited_once_with(
        user_id, holding.account_id, Decimal("-100.00")
    )
    assert result.holdings_updated == 1


@pytest.mark.asyncio
async def test_market_sync_does_not_downgrade_an_existing_quote(monkeypatch):
    user_id = uuid4()
    holding = Holding(
        id=uuid4(), account_id=uuid4(), symbol="VOO", quantity=Decimal("10"),
        cost_basis=Decimal("4000"), market_value=Decimal("5000"),
        asset_class=AssetClass.EQUITY, as_of=date(2026, 9, 21), pricing_mode="automatic",
        last_price=Decimal("500"),
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
