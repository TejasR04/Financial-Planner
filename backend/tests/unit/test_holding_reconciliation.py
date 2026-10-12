from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.domain.entities import Holding
from app.domain.enums import AssetClass
from app.persistence.models import HoldingModel
from app.persistence.repositories.holding_repository import HoldingRepository


def position(account_id, security="security-1", symbol="TEST"):
    return Holding(uuid4(), account_id, symbol, Decimal("2"), Decimal("10"), Decimal("12"),
                   AssetClass.EQUITY, date(2026, 10, 11), last_price=Decimal("6"), provider_security_id=security)


def stored(holding):
    return HoldingModel(id=holding.id, account_id=holding.account_id, symbol=holding.symbol,
                        quantity=holding.quantity, cost_basis=holding.cost_basis,
                        market_value=holding.market_value, asset_class="equity", as_of=holding.as_of,
                        pricing_mode="manual", last_price=holding.last_price,
                        provider_security_id=holding.provider_security_id)


def session_with(rows):
    return SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))),
        add=Mock(), delete=AsyncMock(), flush=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_provider_identity_survives_refresh_and_symbol_change():
    account_id = uuid4()
    old = position(account_id)
    db = session_with([stored(old)])
    incoming = position(account_id, symbol="RENAMED")
    incoming.quantity = Decimal("3")
    result = await HoldingRepository(db).replace_for_accounts([account_id], [incoming])
    assert result[0].id == old.id
    assert result[0].symbol == "RENAMED"
    assert result[0].quantity == Decimal("3")
    db.add.assert_not_called()
    db.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_same_symbol_securities_remain_distinct_and_missing_position_is_deleted():
    account_id = uuid4()
    first, second = position(account_id, "one"), position(account_id, "two")
    first_row, second_row = stored(first), stored(second)
    db = session_with([first_row, second_row])
    result = await HoldingRepository(db).replace_for_accounts([account_id], [position(account_id, "two")])
    assert [item.id for item in result] == [second.id]
    db.delete.assert_awaited_once_with(first_row)


@pytest.mark.asyncio
async def test_unique_legacy_symbol_adopts_security_without_changing_id():
    account_id = uuid4()
    legacy = position(account_id, None)
    db = session_with([stored(legacy)])
    result = await HoldingRepository(db).replace_for_accounts([account_id], [position(account_id)])
    assert result[0].id == legacy.id
    assert result[0].provider_security_id == "security-1"
    db.add.assert_not_called()
