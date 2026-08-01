"""PortfolioAllocationService — analyzes actual vs. target asset allocation
and suggests rebalancing trades. Pure Python, no DB/FastAPI imports.

This was named in the original service list but not yet implemented; it's
also what `FinancialHealthService`'s diversification sub-score and the
`analyze_allocation` AI tool should eventually delegate to instead of
inlining drift math (see the TODO in `app/ai/tools/investment_tools.py`
once that tool is added).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities import Holding
from app.domain.enums import AssetClass

ZERO = Decimal("0")

# Equity is compared against a single "target equity allocation" figure
# throughout the app (see PlanningProfile.target_equity_allocation), so the
# other asset classes are treated as one combined "non-equity" bucket here
# for the headline drift number; the per-class breakdown is still reported
# in full for the frontend's allocation chart.
EQUITY_CLASSES = {AssetClass.EQUITY}


@dataclass(slots=True, frozen=True)
class AllocationBreakdown:
    asset_class: AssetClass
    market_value: Decimal
    weight: Decimal  # fraction of total portfolio, 0-1


@dataclass(slots=True, frozen=True)
class RebalanceSuggestion:
    asset_class: AssetClass
    action: str  # "buy" or "sell"
    amount: Decimal


@dataclass(slots=True, frozen=True)
class AllocationAnalysis:
    total_market_value: Decimal
    breakdown: list[AllocationBreakdown]
    actual_equity_allocation: Decimal
    target_equity_allocation: Decimal
    drift: Decimal  # actual - target; positive = overweight equity
    is_within_tolerance: bool
    rebalance_suggestions: list[RebalanceSuggestion]


class PortfolioAllocationService:
    def analyze(
        self,
        holdings: list[Holding],
        target_equity_allocation: Decimal,
        tolerance: Decimal = Decimal("0.05"),
    ) -> AllocationAnalysis:
        total = sum((h.market_value for h in holdings), ZERO)

        by_class: dict[AssetClass, Decimal] = {}
        for h in holdings:
            by_class[h.asset_class] = by_class.get(h.asset_class, ZERO) + h.market_value

        breakdown = [
            AllocationBreakdown(
                asset_class=asset_class,
                market_value=value,
                weight=(value / total).quantize(Decimal("0.0001")) if total > ZERO else ZERO,
            )
            for asset_class, value in sorted(by_class.items(), key=lambda kv: kv[1], reverse=True)
        ]

        equity_value = sum((v for k, v in by_class.items() if k in EQUITY_CLASSES), ZERO)
        actual_equity_allocation = (equity_value / total).quantize(Decimal("0.0001")) if total > ZERO else ZERO
        drift = actual_equity_allocation - target_equity_allocation
        is_within_tolerance = abs(drift) <= tolerance

        suggestions: list[RebalanceSuggestion] = []
        if total > ZERO and not is_within_tolerance:
            target_equity_value = total * target_equity_allocation
            delta = equity_value - target_equity_value
            if delta > ZERO:
                amount = delta.quantize(Decimal("0.01"))
                suggestions.extend([
                    RebalanceSuggestion(AssetClass.EQUITY, "sell", amount),
                    RebalanceSuggestion(AssetClass.FIXED_INCOME, "buy", amount),
                ])
            else:
                amount = (-delta).quantize(Decimal("0.01"))
                non_equity_classes = [
                    (asset_class, value)
                    for asset_class, value in by_class.items()
                    if asset_class not in EQUITY_CLASSES and value > ZERO
                ]
                # Fund the equity purchase from existing non-equity buckets,
                # largest first, without suggesting a sale larger than the
                # value held in any one class.
                remaining = amount
                for source_class, value in sorted(
                    non_equity_classes, key=lambda item: item[1], reverse=True
                ):
                    sale = min(remaining, value).quantize(Decimal("0.01"))
                    if sale > ZERO:
                        suggestions.append(
                            RebalanceSuggestion(source_class, "sell", sale)
                        )
                        remaining -= sale
                    if remaining <= ZERO:
                        break
                suggestions.append(
                    RebalanceSuggestion(AssetClass.EQUITY, "buy", amount)
                )

        return AllocationAnalysis(
            total_market_value=total,
            breakdown=breakdown,
            actual_equity_allocation=actual_equity_allocation,
            target_equity_allocation=target_equity_allocation,
            drift=drift,
            is_within_tolerance=is_within_tolerance,
            rebalance_suggestions=suggestions,
        )
