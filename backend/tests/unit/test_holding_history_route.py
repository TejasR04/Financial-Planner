from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.routes import investments
from app.domain.entities import User
from app.domain.enums import AccountType, AssetClass
from app.domain.entities import Holding


@pytest.mark.asyncio
async def test_holding_history_is_account_scoped_and_appends_current_value(monkeypatch):
    user = User(uuid4(), "test@example.com", "Test")
    account_id, other_account_id = uuid4(), uuid4()
    account = SimpleNamespace(type=AccountType.INVESTMENT)
    past = date.today() - timedelta(days=1)
    snapshots = SimpleNamespace(holding_history_for_user=AsyncMock(return_value=[(past, Decimal("100"))]))
    current = Holding(
        id=uuid4(), account_id=account_id, symbol="VTI", quantity=Decimal("2"),
        cost_basis=Decimal("90"), market_value=Decimal("120"), asset_class=AssetClass.EQUITY,
        as_of=date.today(),
        last_price=Decimal("60"),
    )
    other = Holding(
        id=uuid4(), account_id=other_account_id, symbol="VTI", quantity=Decimal("8"),
        cost_basis=Decimal("300"), market_value=Decimal("400"), asset_class=AssetClass.EQUITY,
        as_of=date.today(),
        last_price=Decimal("50"),
    )
    monkeypatch.setattr(investments, "AccountRepository", lambda _: SimpleNamespace(get_for_user=AsyncMock(return_value=account)))
    monkeypatch.setattr(investments, "InvestmentValueSnapshotRepository", lambda _: snapshots)
    monkeypatch.setattr(investments, "HoldingRepository", lambda _: SimpleNamespace(list_for_account=AsyncMock(return_value=[current, other])))

    result = await investments.get_holding_history(account_id, " vti ", user, None)

    assert result.account_id == account_id
    assert result.symbol == "VTI"
    assert result.last_price == Decimal("60")
    assert result.price_as_of == current.as_of
    assert [(point.date, point.value) for point in result.history] == [
        (past, Decimal("100")), (date.today(), Decimal("120"))
    ]
    snapshots.holding_history_for_user.assert_awaited_once_with(user.id, account_id, "VTI")


@pytest.mark.asyncio
async def test_holding_history_shows_current_point_when_no_snapshots(monkeypatch):
    user = User(uuid4(), "test@example.com", "Test")
    account_id = uuid4()
    monkeypatch.setattr(investments, "AccountRepository", lambda _: SimpleNamespace(get_for_user=AsyncMock(return_value=SimpleNamespace(type=AccountType.RETIREMENT))))
    monkeypatch.setattr(investments, "InvestmentValueSnapshotRepository", lambda _: SimpleNamespace(holding_history_for_user=AsyncMock(return_value=[])))
    holding = SimpleNamespace(account_id=account_id, symbol="ABC", market_value=Decimal("45.67"))
    monkeypatch.setattr(investments, "HoldingRepository", lambda _: SimpleNamespace(list_for_account=AsyncMock(return_value=[holding])))

    result = await investments.get_holding_history(account_id, "ABC", user, None)
    assert [(point.date, point.value) for point in result.history] == [(date.today(), Decimal("45.67"))]
    assert result.last_price is None
    assert result.price_as_of is None


@pytest.mark.asyncio
async def test_holding_history_orders_dates_and_replaces_today_without_changing_quote_date(monkeypatch):
    user = User(uuid4(), "test@example.com", "Test")
    account_id = uuid4()
    today = date(2026, 9, 28)
    monkeypatch.setattr(investments, "financial_today", lambda: today)
    monkeypatch.setattr(investments, "AccountRepository", lambda _: SimpleNamespace(
        get_for_user=AsyncMock(return_value=SimpleNamespace(type=AccountType.INVESTMENT))))
    monkeypatch.setattr(investments, "InvestmentValueSnapshotRepository", lambda _: SimpleNamespace(
        holding_history_for_user=AsyncMock(return_value=[
            (today, Decimal("999")), (date(2026, 9, 24), Decimal("100")),
            (date(2026, 9, 25), Decimal("110")),
        ])))
    holding = Holding(uuid4(), account_id, "VTI", Decimal("2"), Decimal("90"),
                      Decimal("120"), AssetClass.EQUITY, date(2026, 9, 25), last_price=Decimal("60"))
    monkeypatch.setattr(investments, "HoldingRepository", lambda _: SimpleNamespace(
        list_for_account=AsyncMock(return_value=[holding])))

    result = await investments.get_holding_history(account_id, "VTI", user, None)

    assert [(point.date, point.value) for point in result.history] == [
        (date(2026, 9, 24), Decimal("100")), (date(2026, 9, 25), Decimal("110")),
        (today, Decimal("120")),
    ]
    assert result.last_price == Decimal("60")
    assert result.price_as_of == date(2026, 9, 25)


@pytest.mark.asyncio
async def test_account_history_is_scoped_and_replaces_current_day(monkeypatch):
    user = User(uuid4(), "test@example.com", "Test")
    account_id = uuid4()
    today = date(2026, 9, 28)
    past = today - timedelta(days=1)
    snapshots = SimpleNamespace(account_history_for_user=AsyncMock(return_value=[
        (past, Decimal("100")), (today, Decimal("110")),
    ]))
    account = SimpleNamespace(type=AccountType.RETIREMENT, balance=Decimal("125"))
    account_repo = SimpleNamespace(get_for_user=AsyncMock(return_value=account))
    monkeypatch.setattr(investments, "financial_today", lambda: today)
    monkeypatch.setattr(investments, "AccountRepository", lambda _: account_repo)
    monkeypatch.setattr(investments, "InvestmentValueSnapshotRepository", lambda _: snapshots)
    result = await investments.get_account_history(account_id, user, None)
    account_repo.get_for_user.assert_awaited_once_with(user.id, account_id)
    snapshots.account_history_for_user.assert_awaited_once_with(user.id, account_id)
    assert result.account_id == account_id
    assert [(point.date, point.value) for point in result.history] == [(past, Decimal("100")), (today, Decimal("125"))]


@pytest.mark.asyncio
async def test_account_history_rejects_noninvestment_accounts(monkeypatch):
    from fastapi import HTTPException
    account = SimpleNamespace(type=AccountType.DEPOSITORY)
    monkeypatch.setattr(investments, "AccountRepository", lambda _: SimpleNamespace(get_for_user=AsyncMock(return_value=account)))
    with pytest.raises(HTTPException) as error:
        await investments.get_account_history(uuid4(), User(uuid4(), "test@example.com", "Test"), None)
    assert error.value.status_code == 404
