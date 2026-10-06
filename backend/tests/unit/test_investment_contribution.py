from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from app.domain.investment_contributions import allocate_contribution
from app.services.investment_contribution_service import InvestmentContributionService

from app.services.investment_contribution_service import (
    following_scheduled_date,
    next_scheduled_date,
)


def test_month_end_schedule_does_not_drift_after_february() -> None:
    february = following_scheduled_date(30, date(2027, 1, 30))
    assert february == date(2027, 2, 28)
    assert following_scheduled_date(30, february) == date(2027, 3, 30)


def test_next_schedule_uses_today_or_the_next_month() -> None:
    assert next_scheduled_date(15, date(2026, 9, 15)) == date(2026, 9, 15)
    assert next_scheduled_date(15, date(2026, 9, 16)) == date(2026, 10, 15)


def position(value="1000", quantity="10", basis="800", price=None, identifier=1):
    return SimpleNamespace(
        id=UUID(int=identifier), market_value=Decimal(value), quantity=Decimal(quantity),
        cost_basis=Decimal(basis), last_price=Decimal(price) if price else None,
        asset_class="equity", symbol="VTI", as_of=date(2026, 9, 30),
    )


def test_contribution_increases_shares_and_basis_without_inventing_a_gain():
    holdings = [position("600", "6", "500", "100"), position("400", "4", "300", identifier=2)]
    allocate_contribution(holdings, Decimal("250"))
    assert [h.market_value for h in holdings] == [Decimal("750"), Decimal("500")]
    assert [h.quantity for h in holdings] == [Decimal("7.5"), Decimal("5")]
    assert [h.cost_basis for h in holdings] == [Decimal("650"), Decimal("400")]
    assert sum(h.market_value - h.cost_basis for h in holdings) == Decimal("200")
    # The next automatic quote at the same price retains the deposited value.
    assert holdings[0].quantity * holdings[0].last_price == holdings[0].market_value
    assert holdings[0].as_of == date(2026, 9, 30)


def test_cent_rounding_preserves_the_total_even_with_many_tiny_positions():
    holdings = [position("1", "1", "1", identifier=i) for i in range(1, 101)]
    allocate_contribution(holdings, Decimal("0.51"))
    assert sum(h.market_value for h in holdings) == Decimal("100.51")
    assert all(h.market_value >= 1 for h in holdings)


def test_closed_positions_and_unknown_basis_stay_unknown():
    holdings = [position(basis="0"), position("0", "0", "0", identifier=2)]
    allocate_contribution(holdings, Decimal("250"))
    assert holdings[0].market_value == Decimal("1250")
    assert holdings[0].cost_basis == 0
    assert holdings[1].market_value == 0


def test_automatic_position_without_a_share_price_leaves_money_for_cash():
    holding = position(quantity="0")
    holding.pricing_mode = "automatic"
    assert allocate_contribution([holding], Decimal("250")) == Decimal("250")
    assert holding.market_value == Decimal("1000")


@pytest.mark.asyncio
async def test_due_contributions_update_holdings_and_snapshots_once(monkeypatch):
    import app.services.investment_contribution_service as module

    monkeypatch.setattr(module, "contribution_today", lambda: date(2026, 10, 5))
    account = SimpleNamespace(id=uuid4(), balance=Decimal("1000"))
    rule = SimpleNamespace(id=uuid4(), amount=Decimal("250"), next_run_date=date(2026, 9, 5), day_of_month=5)
    holding = position(price="100")
    session = SimpleNamespace(
        execute=AsyncMock(side_effect=[
            SimpleNamespace(all=lambda: [(rule, account)]),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [holding])),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [holding])),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [])),
            SimpleNamespace(all=lambda: [(rule, account)]),
        ]),
        scalar=AsyncMock(return_value=None), add=Mock(), flush=AsyncMock(),
    )
    service = InvestmentContributionService(session)
    service.accounts.get_for_user = AsyncMock(return_value=account)
    service.history.record_for_accounts = AsyncMock()
    service.history.record_holding_values = AsyncMock()
    user_id = uuid4()
    assert await service.apply(user_id) == 2
    assert await service.apply(user_id) == 0
    assert account.balance == holding.market_value == Decimal("1500")
    assert holding.quantity == Decimal("15")
    assert holding.cost_basis == Decimal("1300")
    assert session.add.call_count == 2
    service.history.record_holding_values.assert_awaited_once()


@pytest.mark.asyncio
async def test_accounts_without_holdings_receive_a_cash_position():
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))),
        add=Mock(),
        flush=AsyncMock(),
    )
    await InvestmentContributionService(session)._add_to_holdings(uuid4(), Decimal("250"), date(2026, 10, 5))
    cash = session.add.call_args.args[0]
    assert cash.symbol == "CUR:USD"
    assert cash.market_value == cash.quantity == cash.cost_basis == Decimal("250")
    assert cash.pricing_mode == "manual"


@pytest.mark.asyncio
async def test_increasing_a_manual_account_balance_allocates_only_the_new_money(monkeypatch):
    from app.persistence.repositories import account_repository as module

    row = SimpleNamespace(
        id=uuid4(), user_id=uuid4(), institution_id=None, name="Manual IRA", type="retirement",
        balance=Decimal("1000"), currency="USD", mask=None, apy=None, status="manual",
        updated_at=None, external_account_id=None, archived_at=None,
    )
    add = AsyncMock()
    monkeypatch.setattr(module, "HoldingRepository", lambda _: SimpleNamespace(add_contribution=add))
    repository = module.AccountRepository(SimpleNamespace(flush=AsyncMock()))
    repository._row_for_user = AsyncMock(return_value=row)
    await repository.update_for_user(row.user_id, row.id, balance=Decimal("1250"))
    await repository.update_for_user(row.user_id, row.id, balance=Decimal("1250"))
    await repository.rename_for_user(row.user_id, row.id, "IRA")
    assert add.await_count == 1
    assert add.await_args.args[:2] == (row.id, Decimal("250"))
