from datetime import date
from decimal import Decimal

import pytest

from app.domain.enums import AssetClass
from app.schemas.financial_inputs import HoldingInput, HoldingUpdate


def test_holding_symbols_are_trimmed_and_normalized_on_create_and_update():
    created = HoldingInput(
        symbol="  vti ", quantity=Decimal("1"), cost_basis=Decimal("1"),
        market_value=Decimal("1"), asset_class=AssetClass.EQUITY, as_of=date.today(),
    )
    updated = HoldingUpdate(symbol="  vti ")

    assert created.symbol == "VTI"
    assert updated.symbol == "VTI"


@pytest.mark.parametrize("schema", [HoldingInput, HoldingUpdate])
@pytest.mark.parametrize("symbol", ["   ", "\t\n"])
def test_holding_symbol_rejects_empty_after_trimming(schema, symbol):
    with pytest.raises(ValueError, match="non-whitespace"):
        if schema is HoldingInput:
            schema(
                symbol=symbol, quantity=Decimal("1"), cost_basis=Decimal("1"),
                market_value=Decimal("1"), asset_class=AssetClass.EQUITY, as_of=date.today(),
            )
        else:
            schema(symbol=symbol)
