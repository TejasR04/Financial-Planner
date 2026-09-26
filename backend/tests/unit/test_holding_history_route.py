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
    )
    other = Holding(
        id=uuid4(), account_id=other_account_id, symbol="VTI", quantity=Decimal("8"),
        cost_basis=Decimal("300"), market_value=Decimal("400"), asset_class=AssetClass.EQUITY,
        as_of=date.today(),
    )
    monkeypatch.setattr(investments, "AccountRepository", lambda _: SimpleNamespace(get_for_user=AsyncMock(return_value=account)))
    monkeypatch.setattr(investments, "InvestmentValueSnapshotRepository", lambda _: snapshots)
    monkeypatch.setattr(investments, "HoldingRepository", lambda _: SimpleNamespace(list_for_account=AsyncMock(return_value=[current, other])))

    result = await investments.get_holding_history(account_id, " vti ", user, None)

    assert result.account_id == account_id
    assert result.symbol == "VTI"
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
