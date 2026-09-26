"""Quantified checks from current balances and shared historical averages."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities import FinancialSnapshot
from app.domain.enums import InsightKind
from decimal import Decimal
from app.domain.enums import AssetClass
from app.services.activity_history import ActivityHistory


@dataclass(slots=True, frozen=True)
class InsightDraft:
    kind: InsightKind
    text: str
    meta: str


class InsightService:
    def generate(
        self,
        snapshot: FinancialSnapshot,
        history: ActivityHistory,
        monthly_cash_flow: tuple[Decimal, Decimal] | None = None,
    ) -> list[InsightDraft]:
        drafts: list[InsightDraft] = []

        zero = Decimal("0")
        # Callers that load the authoritative activity summary pass its
        # virtually classified budget cash flow. Keep the fallback for other
        # callers that only have raw transaction history.
        income, expenses = monthly_cash_flow or history.monthly_cash_flow
        if history.months:
            drafts.append(InsightDraft(
                InsightKind.ALERT if income < expenses else InsightKind.OBSERVATION,
                f"Average monthly income is ${income:,.2f} and expenses are ${expenses:,.2f}, "
                f"leaving ${income - expenses:,.2f} per month. Transfers and card payments are excluded.",
                history.label,
            ))
            if expenses > zero:
                cash = snapshot.liquid_assets
                months = cash / expenses
                drafts.append(InsightDraft(
                    InsightKind.ALERT if months < 6 else InsightKind.OBSERVATION,
                    f"Accessible depository balances and taxable brokerage cash total ${cash:,.2f}, covering "
                    f"{months:.1f} months at your ${expenses:,.2f} average monthly expense level. "
                    "This check uses a six-month reference and excludes cash in retirement accounts.",
                    f"Current cash / {history.label}",
                ))
            target = snapshot.profile.target_savings_rate
            if income > zero and target is not None:
                rate = (income - expenses) / income
                drafts.append(InsightDraft(
                    InsightKind.OBSERVATION if rate >= target else InsightKind.ALERT,
                    f"You retained {rate:.1%} of recorded income after expenses, "
                    f"compared with your saved savings target of {target:.1%}.",
                    f"Savings / {history.label}",
                ))
        else:
            drafts.append(InsightDraft(
                InsightKind.OBSERVATION,
                "Spending, savings-rate, and cash-buffer checks need a completed month of transaction history. "
                "The current month and the first partially imported month are excluded.",
                "Insufficient transaction history",
            ))
        assets = sum((account.balance for account in snapshot.accounts if not account.is_liability), zero)
        debt = sum((abs(account.balance) for account in snapshot.accounts if account.is_liability), zero)
        if assets > zero and debt > zero:
            drafts.append(InsightDraft(
                InsightKind.ALERT if debt / assets > Decimal("0.5") else InsightKind.OBSERVATION,
                f"Debt balances total ${debt:,.2f}, or {debt / assets:.1%} of your ${assets:,.2f} in assets. "
                "This compares balances only; it does not assess interest rates.",
                f"Current account balances as of {snapshot.as_of}",
            ))
        total = sum((holding.market_value for holding in snapshot.holdings), zero)
        if total > zero:
            equity = sum((holding.market_value for holding in snapshot.holdings
                          if holding.asset_class == AssetClass.EQUITY), zero) / total
            target = snapshot.profile.target_equity_allocation
            drafts.append(InsightDraft(
                InsightKind.OPPORTUNITY if abs(equity - target) > Decimal("0.05") else InsightKind.OBSERVATION,
                f"Equities are {equity:.1%} of ${total:,.2f} in reported holdings, compared with your "
                f"{target:.1%} target ({abs(equity - target) * 100:.1f} percentage points "
                f"{'above' if equity >= target else 'below'}). Accounts without reported holdings are excluded.",
                f"Current reported holdings as of {snapshot.as_of}",
            ))
        return drafts
