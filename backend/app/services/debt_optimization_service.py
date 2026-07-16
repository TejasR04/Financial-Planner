"""DebtOptimizationService — avalanche/snowball payoff planning.

Backs `prioritize_debt_payoff` (AI tool) and any `/simulations/debt*` route.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities import Liability
from app.domain.enums import DebtPayoffStrategy

ZERO = Decimal("0")


@dataclass(slots=True, frozen=True)
class DebtPayoffMonth:
    month_index: int
    liability_id: str
    payment: Decimal
    remaining_balance: Decimal


@dataclass(slots=True, frozen=True)
class DebtPayoffPlan:
    strategy: DebtPayoffStrategy
    months_to_debt_free: int
    total_interest_paid: Decimal
    payoff_order: list[str]  # liability ids, in the order they're eliminated
    schedule: list[DebtPayoffMonth]


class DebtOptimizationService:
    def optimize(
        self,
        liabilities: list[Liability],
        extra_monthly_payment: Decimal,
        strategy: DebtPayoffStrategy = DebtPayoffStrategy.AVALANCHE,
        max_months: int = 600,
    ) -> DebtPayoffPlan:
        """Simulates month by month: every liability gets its minimum
        payment; any `extra_monthly_payment` (plus the minimums freed up by
        payoffs already achieved) is rolled onto the single highest-priority
        liability per the chosen strategy — the standard debt-avalanche /
        debt-snowball rolling-payment method.
        """
        if not liabilities:
            return DebtPayoffPlan(strategy, 0, ZERO, [], [])

        balances = {str(i): l.principal for i, l in enumerate(liabilities)}
        monthly_rates = {str(i): l.interest_rate / Decimal(12) for i, l in enumerate(liabilities)}
        minimums = {str(i): l.minimum_payment for i, l in enumerate(liabilities)}
        priority_key = (
            (lambda i: -liabilities[int(i)].interest_rate)
            if strategy == DebtPayoffStrategy.AVALANCHE
            else (lambda i: liabilities[int(i)].principal)
        )

        schedule: list[DebtPayoffMonth] = []
        payoff_order: list[str] = []
        total_interest = ZERO
        month = 0
        freed_up_minimums = ZERO

        while any(b > ZERO for b in balances.values()) and month < max_months:
            month += 1
            active_ids = [i for i, b in balances.items() if b > ZERO]
            ordered = sorted(active_ids, key=priority_key)
            focus_id = ordered[0]

            for lid in active_ids:
                rate = monthly_rates[lid]
                interest = (balances[lid] * rate).quantize(Decimal("0.01"))
                total_interest += interest
                balances[lid] += interest

                payment = minimums[lid]
                if lid == focus_id:
                    payment += extra_monthly_payment + freed_up_minimums
                payment = min(payment, balances[lid])
                balances[lid] -= payment

                schedule.append(DebtPayoffMonth(month, lid, payment.quantize(Decimal("0.01")), balances[lid]))

                if balances[lid] <= ZERO and lid not in payoff_order:
                    payoff_order.append(lid)
                    freed_up_minimums += minimums[lid]

        return DebtPayoffPlan(
            strategy=strategy,
            months_to_debt_free=month,
            total_interest_paid=total_interest.quantize(Decimal("0.01")),
            payoff_order=payoff_order,
            schedule=schedule,
        )
