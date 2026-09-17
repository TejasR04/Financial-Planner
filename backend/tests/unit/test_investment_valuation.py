from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.entities import Account, Holding, User
from app.domain.enums import AccountType, AssetClass
from app.domain.holding_valuation import holding_asset_class, unrealized_gain_loss
from app.api.v1.routes import investments
from app.persistence.repositories.holding_repository import _to_domain


@pytest.mark.parametrize("symbol", ["CUR:USD", "cur:usd", "SPAXX"])
def test_cash_positions_are_not_equity_gains_even_for_legacy_imports(symbol):
    assert holding_asset_class(symbol, AssetClass.EQUITY) == AssetClass.CASH
    assert unrealized_gain_loss(symbol, AssetClass.EQUITY, Decimal(0), Decimal(10000)) is None
    assert unrealized_gain_loss(symbol, AssetClass.EQUITY, Decimal(9000), Decimal(10000)) is None
    holding = _to_domain(SimpleNamespace(id=uuid4(), account_id=uuid4(), symbol=symbol,
        asset_class="equity", quantity=Decimal(10000), cost_basis=Decimal(0), market_value=Decimal(10000), as_of=date.today()))
    assert holding.asset_class == AssetClass.CASH


def test_unavailable_basis_is_not_profit_and_real_losses_are_preserved():
    assert unrealized_gain_loss("VTI", AssetClass.EQUITY, Decimal(0), Decimal(500)) is None
    assert unrealized_gain_loss("VTI", AssetClass.EQUITY, Decimal(600), Decimal(500)) == -100


@pytest.mark.asyncio
async def test_dashboard_gain_totals_only_include_eligible_holdings(monkeypatch):
    user = User(uuid4(), "test@example.com", "Test")
    account = Account(uuid4(), user.id, "Brokerage", AccountType.INVESTMENT, Decimal(20000))
    holdings = [Holding(uuid4(), account.id, symbol, Decimal(1), Decimal(cost), Decimal(value), cls, date.today())
                for symbol, cost, value, cls in [
                    ("VTI", "1000", "1200", AssetClass.EQUITY),
                    ("SPAXX", "0", "10000", AssetClass.CASH),
                    ("CUR:USD", "0", "5000", AssetClass.CASH),
                    ("UNKNOWN", "0", "3000", AssetClass.EQUITY),
                ]]
    for name, repo in {
        "AccountRepository": SimpleNamespace(list_for_user=AsyncMock(return_value=[account])),
        "InstitutionRepository": SimpleNamespace(list_for_user=AsyncMock(return_value=[])),
        "HoldingRepository": SimpleNamespace(list_for_user=AsyncMock(return_value=holdings)),
        "InvestmentValueSnapshotRepository": SimpleNamespace(daily_totals_for_user=AsyncMock(return_value=[])),
    }.items():
        monkeypatch.setattr(investments, name, lambda db, repo=repo: repo)
    result = await investments.get_investment_dashboard(user, None)
    assert result.total_value == 20000
    assert result.total_holdings_value == 19200
    assert result.total_cost_basis == 1000
    assert result.total_gain_loss == 200
    assert result.excluded_gain_loss_value == 18000
    assert result.gain_loss_holding_count == 1
    assert all(h.gain_loss is None and h.cost_basis is None for h in result.holdings if h.symbol != "VTI")
    holdings.pop(0)
    assert (await investments.get_investment_dashboard(user, None)).total_gain_loss is None
