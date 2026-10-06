"""Allocate contributions without losing cents or treating deposits as gains."""
from decimal import Decimal, ROUND_HALF_UP


def allocate_contribution(holdings, amount: Decimal) -> Decimal:
    positions = sorted(
        [holding for holding in holdings if holding.market_value > 0 and (
            getattr(holding, "pricing_mode", "manual") != "automatic"
            or holding.quantity > 0 or (holding.last_price is not None and holding.last_price > 0)
        )],
        key=lambda holding: str(holding.id),
    )
    total = sum((holding.market_value for holding in positions), Decimal("0"))
    remaining = amount
    for index, holding in enumerate(positions):
        added = remaining if index == len(positions) - 1 else (
            amount * holding.market_value / total
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # Capping prevents many small positions from rounding past the deposit.
        added = min(added, remaining)
        remaining -= added
        price = holding.last_price
        if price is None or price <= 0:
            price = holding.market_value / holding.quantity if holding.quantity > 0 else None
        if price is not None:
            holding.quantity += (added / price).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        if holding.cost_basis > 0 or holding.asset_class == "cash":
            holding.cost_basis += added
        # An unknown historical basis stays unknown instead of fabricating gains.
        holding.market_value += added
    return remaining
