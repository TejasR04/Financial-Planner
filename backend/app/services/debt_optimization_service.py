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
        if extra_monthly_payment < ZERO:
            raise ValueError("extra_monthly_payment must be non-negative")

        balances = {str(i): l.principal for i, l in enumerate(liabilities)}
        monthly_rates = {str(i): l.interest_rate / Decimal(12) for i, l in enumerate(liabilities)}
        minimums = {str(i): l.minimum_payment for i, l in enumerate(liabilities)}
        total_monthly_budget = sum(minimums.values(), ZERO) + extra_monthly_payment

        def ordered_active() -> list[str]:
            active = [i for i, balance in balances.items() if balance > ZERO]
            if strategy == DebtPayoffStrategy.AVALANCHE:
                return sorted(
                    active,
                    key=lambda i: (
                        -liabilities[int(i)].interest_rate,
                        balances[i],
                        int(i),
                    ),
                )
            return sorted(active, key=lambda i: (balances[i], int(i)))

        schedule: list[DebtPayoffMonth] = []
        payoff_order: list[str] = []
        total_interest = ZERO
        month = 0
        while any(b > ZERO for b in balances.values()) and month < max_months:
            month += 1
            active_ids = [i for i, b in balances.items() if b > ZERO]
            payments = {i: ZERO for i in active_ids}

            # Interest accrues before this month's payments.
            for lid in active_ids:
                rate = monthly_rates[lid]
                interest = (balances[lid] * rate).quantize(Decimal("0.01"))
                total_interest += interest
                balances[lid] += interest

            # Preserve one fixed monthly payment budget. Minimum payments are
            # made once, and any unused portion (including payoff overage) is
            # immediately available to the priority waterfall.
            remaining_budget = total_monthly_budget
            for lid in active_ids:
                payment = min(minimums[lid], balances[lid], remaining_budget)
                balances[lid] -= payment
                payments[lid] += payment
                remaining_budget -= payment

            while remaining_budget > ZERO:
                ordered = ordered_active()
                if not ordered:
                    break
                lid = ordered[0]
                payment = min(remaining_budget, balances[lid])
                balances[lid] -= payment
                payments[lid] += payment
                remaining_budget -= payment

            newly_paid = [
                lid for lid in active_ids
                if balances[lid] <= ZERO and lid not in payoff_order
            ]
            if strategy == DebtPayoffStrategy.AVALANCHE:
                newly_paid.sort(
                    key=lambda i: (-liabilities[int(i)].interest_rate, int(i))
                )
            else:
                newly_paid.sort(key=int)
            payoff_order.extend(newly_paid)

            for lid in active_ids:
                schedule.append(
                    DebtPayoffMonth(
                        month,
                        lid,
                        payments[lid].quantize(Decimal("0.01")),
                        balances[lid].quantize(Decimal("0.01")),
                    )
                )

        return DebtPayoffPlan(
            strategy=strategy,
            months_to_debt_free=month,
            total_interest_paid=total_interest.quantize(Decimal("0.01")),
            payoff_order=payoff_order,
            schedule=schedule,
        )
