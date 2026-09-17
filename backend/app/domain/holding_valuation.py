"""Cash classification and conservative gain/loss eligibility."""
from decimal import Decimal

from app.domain.enums import AssetClass


def holding_asset_class(symbol: str, asset_class: AssetClass) -> AssetClass:
    # Also correct older imports where currency and SPAXX were securities.
    symbol = symbol.strip().upper()
    if symbol.startswith("CUR:") or symbol == "SPAXX":
        return AssetClass.CASH
    return asset_class


def unrealized_gain_loss(symbol: str, asset_class: AssetClass, cost_basis: Decimal,
                         market_value: Decimal) -> Decimal | None:
    # Imported null bases have historically been stored as zero. Do not
    # present the whole position as profit or invent a cash cost basis.
    if holding_asset_class(symbol, asset_class) == AssetClass.CASH or cost_basis <= 0:
        return None
    return market_value - cost_basis
