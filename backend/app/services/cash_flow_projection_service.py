"""CashFlowProjectionService — forward-looking monthly income vs. expenses.

Backs the Overview page's cash-flow chart and the `forecast_cash_flow` AI
tool. Distinct from raw transaction history: this projects forward using
`IncomeSource.growth_rate` and a flat or inflated expense base, rather than
replaying past transactions.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities import IncomeSource
from app.simulation.engine import inflate

ZERO = Decimal("0")
MONTHS_PER_YEAR = 12


@dataclass(slots=True, frozen=True)
class CashFlowMonthPoint:
    month_index: int
    income: Decimal
    expenses: Decimal
    net: Decimal


@dataclass(slots=True, frozen=True)
class CashFlowProjection:
    series: list[CashFlowMonthPoint]
    average_monthly_surplus: Decimal
    projected_savings_rate: Decimal


class CashFlowProjectionService:
    def project(
        self,
        income_sources: list[IncomeSource],
        monthly_expenses: Decimal,
        months: int,
        inflation_rate: Decimal = Decimal("0.028"),
    ) -> CashFlowProjection:
        if months <= 0:
            raise ValueError("months must be positive")

        active_sources = [s for s in income_sources if s.active]
        series: list[CashFlowMonthPoint] = []

        for m in range(1, months + 1):
            years_elapsed = (m - 1) // MONTHS_PER_YEAR
            monthly_income = ZERO
            for source in active_sources:
                grown_annual = source.annual_amount * (Decimal("1") + source.growth_rate) ** years_elapsed
                monthly_income += grown_annual / Decimal(MONTHS_PER_YEAR)

            expenses_this_month = inflate(monthly_expenses, inflation_rate, years_elapsed)
            net = monthly_income - expenses_this_month
            series.append(
                CashFlowMonthPoint(
                    month_index=m,
                    income=monthly_income.quantize(Decimal("0.01")),
                    expenses=expenses_this_month.quantize(Decimal("0.01")),
                    net=net.quantize(Decimal("0.01")),
                )
            )

        total_income = sum((p.income for p in series), ZERO)
        total_net = sum((p.net for p in series), ZERO)
        avg_surplus = (total_net / months).quantize(Decimal("0.01"))
        savings_rate = (total_net / total_income).quantize(Decimal("0.0001")) if total_income > ZERO else ZERO

        return CashFlowProjection(
            series=series,
            average_monthly_surplus=avg_surplus,
            projected_savings_rate=savings_rate,
        )
