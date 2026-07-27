"""Build the privacy-limited, user-specific context supplied to Gemini."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import FinancialSnapshot
from app.domain.enums import AccountType, TransactionType
from app.persistence.repositories.transaction_repository import TransactionRepository


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


async def build_user_financial_context(
    session: AsyncSession, snapshot: FinancialSnapshot
) -> str:
    """Return current planning facts without identifiers or transaction detail."""
    today = date.today()
    start_month_index = today.year * 12 + today.month - 1 - 11
    start = date(start_month_index // 12, start_month_index % 12 + 1, 1)
    transactions = await TransactionRepository(session).list_since_for_income_expense(
        snapshot.user.id, start
    )

    income = sum(
        (abs(item.amount) for item in transactions if item.type == TransactionType.INCOME),
        Decimal("0"),
    )
    expenses = sum(
        (abs(item.amount) for item in transactions if item.type == TransactionType.EXPENSE),
        Decimal("0"),
    )
    contributions = sum(
        (abs(item.amount) for item in transactions if item.type == TransactionType.CONTRIBUTION),
        Decimal("0"),
    )
    months = Decimal("12")
    monthly_income = income / months
    monthly_expenses = expenses / months
    monthly_surplus = monthly_income - monthly_expenses

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
            "average_monthly_income_trailing_12_months": _money(monthly_income),
            "average_monthly_expenses_trailing_12_months": _money(monthly_expenses),
            "average_monthly_surplus_trailing_12_months": _money(monthly_surplus),
            "recorded_contributions_trailing_12_months": _money(contributions),
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
                "principal": _money(liability.principal),
                "interest_rate": str(liability.interest_rate),
                "minimum_payment": _money(liability.minimum_payment),
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
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)
