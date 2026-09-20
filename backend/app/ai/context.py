"""Build the privacy-limited, user-specific context supplied to Gemini."""
from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import FinancialSnapshot
from app.domain.enums import AccountType, TransactionType
from app.persistence.activity_history import load_budget_activity_summary
from app.ai.relevant_activity import build_relevant_activity_context


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


async def build_user_financial_context(
    session: AsyncSession, snapshot: FinancialSnapshot, message: str | None = None
) -> str:
    """Return current planning facts without identifiers or transaction detail."""
    history, (monthly_income, monthly_expenses) = await load_budget_activity_summary(
        session, snapshot.user.id, snapshot.as_of
    )
    monthly_surplus = monthly_income - monthly_expenses
    has_history = bool(history.months)
    contributions = sum(
        (
            abs(row.amount)
            for row in history.transactions
            if row.type == TransactionType.CONTRIBUTION
            and row.posted_at is not None
            and row.posted_at.replace(day=1) in set(history.months)
        ),
        Decimal("0"),
    )

    positive_accounts = [
        account
        for account in snapshot.accounts
        if not account.is_liability and account.balance > 0
    ]
    liability_accounts = [account for account in snapshot.accounts if account.is_liability]
    total_assets = sum((account.balance for account in positive_accounts), Decimal("0"))
    total_liabilities = sum((abs(account.balance) for account in liability_accounts), Decimal("0"))
    retirement_balance = sum(
        (
            account.balance
            for account in snapshot.accounts
            if account.type == AccountType.RETIREMENT and account.balance > 0
        ),
        Decimal("0"),
    )

    payload = {
        "as_of": snapshot.as_of.isoformat(),
        "currency": "USD",
        "display_basis": "real_today_dollars",
        "current_age": snapshot.user.age_on(snapshot.as_of),
        "planning_profile": {
            "target_retirement_age": snapshot.profile.target_retirement_age,
            "target_equity_allocation": str(snapshot.profile.target_equity_allocation),
            "default_withdrawal_rate": str(snapshot.profile.default_withdrawal_rate),
            "expected_real_return": str(snapshot.profile.expected_return),
            "inflation_rate": str(snapshot.profile.inflation_rate),
            "include_social_security": snapshot.profile.include_social_security,
        },
        "summary": {
            "net_worth": _money(snapshot.net_worth),
            "total_assets": _money(total_assets),
            "total_liabilities": _money(total_liabilities),
            "liquid_assets": _money(snapshot.liquid_assets),
            "retirement_account_balance": _money(retirement_balance),
            "average_monthly_classified_income_completed_history": _money(monthly_income) if has_history else None,
            "average_monthly_budget_spending_completed_history": _money(monthly_expenses) if has_history else None,
            "average_monthly_budget_surplus_completed_history": _money(monthly_surplus) if has_history else None,
            "history_window": history.label,
            "recorded_contributions_completed_history": _money(contributions) if has_history else None,
        },
        "accounts": [
            {
                "name": account.name,
                "type": account.type.value,
                "balance": _money(account.balance),
            }
            for account in snapshot.accounts
        ],
        "holdings": [
            {
                "symbol": holding.symbol,
                "market_value": _money(holding.market_value),
                "asset_class": holding.asset_class.value,
            }
            for holding in sorted(
                snapshot.holdings, key=lambda item: item.market_value, reverse=True
            )[:50]
        ],
        "debts": [
            {
                "principal": _money(liability.principal) if liability.principal is not None else None,
                "interest_rate": str(liability.interest_rate) if liability.interest_rate is not None else None,
                "minimum_payment": _money(liability.minimum_payment) if liability.minimum_payment is not None else None,
                "term_months": liability.term_months,
            }
            for liability in snapshot.liabilities
        ],
        "income_sources": [
            {
                "name": source.name,
                "annual_amount": _money(source.annual_amount),
                "growth_rate": str(source.growth_rate),
            }
            for source in snapshot.income_sources
            if source.active
        ],
    }
    if message:
        requested_activity = await build_relevant_activity_context(
            session, snapshot.user.id, message, snapshot.as_of
        )
        if requested_activity:
            payload["requested_activity"] = requested_activity
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)
