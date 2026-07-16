"""FinancialHealthService — composite score behind the Insights page.

Sub-scores are each 0-100 and combined into an overall score with fixed
weights. Every sub-score is a deterministic function of the snapshot — no
external calls, no LLM.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities import FinancialSnapshot
from app.domain.enums import AccountType

ZERO = Decimal("0")
WEIGHTS = {
    "liquidity": Decimal("0.25"),
    "diversification": Decimal("0.25"),
    "debt_ratio": Decimal("0.25"),
    "savings_discipline": Decimal("0.25"),
}


@dataclass(slots=True, frozen=True)
class FinancialHealthScore:
    overall: int
    liquidity: int
    diversification: int
    debt_ratio: int
    savings_discipline: int


class FinancialHealthService:
    def score(
        self,
        snapshot: FinancialSnapshot,
        monthly_expenses: Decimal,
        target_savings_rate: Decimal,
        actual_savings_rate: Decimal,
        target_equity_allocation: Decimal,
        actual_equity_allocation: Decimal,
    ) -> FinancialHealthScore:
        liquidity = self._liquidity_score(snapshot, monthly_expenses)
        diversification = self._diversification_score(target_equity_allocation, actual_equity_allocation)
        debt_ratio = self._debt_ratio_score(snapshot)
        savings_discipline = self._savings_discipline_score(target_savings_rate, actual_savings_rate)

        overall = int(
            (
                Decimal(liquidity) * WEIGHTS["liquidity"]
                + Decimal(diversification) * WEIGHTS["diversification"]
                + Decimal(debt_ratio) * WEIGHTS["debt_ratio"]
                + Decimal(savings_discipline) * WEIGHTS["savings_discipline"]
            ).to_integral_value()
        )

        return FinancialHealthScore(
            overall=overall,
            liquidity=liquidity,
            diversification=diversification,
            debt_ratio=debt_ratio,
            savings_discipline=savings_discipline,
        )

    def _liquidity_score(self, snapshot: FinancialSnapshot, monthly_expenses: Decimal) -> int:
        """100 at >= 6 months of expenses held liquid, scaling linearly to 0."""
        if monthly_expenses <= ZERO:
            return 50
        months_covered = snapshot.liquid_assets / monthly_expenses
        target_months = Decimal("6")
        score = min(Decimal("100"), (months_covered / target_months) * Decimal("100"))
        return int(score.to_integral_value())

    def _diversification_score(self, target: Decimal, actual: Decimal) -> int:
        """100 at zero drift from target equity allocation, decaying with
        the size of the drift."""
        drift = abs(actual - target)
        score = max(Decimal("0"), Decimal("100") - drift * Decimal("500"))
        return int(score.to_integral_value())

    def _debt_ratio_score(self, snapshot: FinancialSnapshot) -> int:
        """100 at debt-to-asset ratio of 0, scaling down to 0 at a ratio of
        1 or worse (liabilities >= assets)."""
        assets = sum((a.balance for a in snapshot.accounts if a.balance > 0), ZERO)
        liabilities = sum((-a.balance for a in snapshot.accounts if a.balance < 0), ZERO)
        if assets <= ZERO:
            return 0
        ratio = min(Decimal("1"), liabilities / assets)
        score = (Decimal("1") - ratio) * Decimal("100")
        return int(score.to_integral_value())

    def _savings_discipline_score(self, target: Decimal, actual: Decimal) -> int:
        """100 at or above target savings rate, scaling down proportionally
        below target."""
        if target <= ZERO:
            return 100
        score = min(Decimal("100"), (actual / target) * Decimal("100"))
        return int(max(Decimal("0"), score).to_integral_value())
