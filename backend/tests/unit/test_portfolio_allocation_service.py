from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.domain.entities import Holding
from app.domain.enums import AssetClass
from app.services.portfolio_allocation_service import PortfolioAllocationService


def _holding(asset_class: AssetClass, value: Decimal) -> Holding:
    return Holding(
        id=uuid4(), account_id=uuid4(), symbol="TEST", quantity=Decimal("1"),
        cost_basis=value, market_value=value, asset_class=asset_class, as_of=date.today(),
    )


def test_allocation_within_tolerance_produces_no_suggestions():
    service = PortfolioAllocationService()
    holdings = [
        _holding(AssetClass.EQUITY, Decimal("60000")),
        _holding(AssetClass.FIXED_INCOME, Decimal("40000")),
    ]
    result = service.analyze(holdings, target_equity_allocation=Decimal("0.60"))
    assert result.actual_equity_allocation == Decimal("0.6000")
    assert result.is_within_tolerance is True
    assert result.rebalance_suggestions == []


def test_overweight_equity_suggests_sell():
    service = PortfolioAllocationService()
    holdings = [
        _holding(AssetClass.EQUITY, Decimal("90000")),
        _holding(AssetClass.FIXED_INCOME, Decimal("10000")),
    ]
    result = service.analyze(holdings, target_equity_allocation=Decimal("0.60"))
    assert result.is_within_tolerance is False
    assert result.rebalance_suggestions[0].action == "sell"
    assert result.rebalance_suggestions[0].asset_class == AssetClass.EQUITY


def test_underweight_equity_suggests_buy():
    service = PortfolioAllocationService()
    holdings = [
        _holding(AssetClass.EQUITY, Decimal("20000")),
        _holding(AssetClass.FIXED_INCOME, Decimal("80000")),
    ]
    result = service.analyze(holdings, target_equity_allocation=Decimal("0.60"))
    assert result.rebalance_suggestions[0].action == "buy"


def test_empty_portfolio_does_not_divide_by_zero():
    service = PortfolioAllocationService()
    result = service.analyze([], target_equity_allocation=Decimal("0.60"))
    assert result.total_market_value == Decimal("0")
    assert result.actual_equity_allocation == Decimal("0")
    assert result.breakdown == []
