from decimal import Decimal

from pydantic import BaseModel

from app.ai.tool_registry import registry
from app.simulation.engine import calculate_amortized_payment

MAX_FRONT_END_DTI = Decimal("0.28")   # housing payment / gross monthly income
MAX_BACK_END_DTI = Decimal("0.36")     # total debt payments / gross monthly income


class EstimateHomeAffordabilityInput(BaseModel):
    gross_monthly_income: Decimal
    existing_monthly_debt_payments: Decimal
    down_payment: Decimal
    mortgage_rate: Decimal = Decimal("0.065")
    term_months: int = 360
    property_tax_and_insurance_rate: Decimal = Decimal("0.015")  # annual, % of home price


@registry.register(
    "estimate_home_affordability",
    "Estimate a maximum affordable home price given income, existing debt "
    "payments, a down payment, and a mortgage rate, using standard "
    "front-end/back-end debt-to-income ratios.",
    EstimateHomeAffordabilityInput,
)
def estimate_home_affordability(args: EstimateHomeAffordabilityInput):
    max_housing_payment_front = args.gross_monthly_income * MAX_FRONT_END_DTI
    max_total_debt_back = args.gross_monthly_income * MAX_BACK_END_DTI
    max_housing_payment_back = max_total_debt_back - args.existing_monthly_debt_payments
    max_housing_payment = max(Decimal("0"), min(max_housing_payment_front, max_housing_payment_back))

    # Solve for home price such that P&I + tax/insurance <= max_housing_payment.
    # tax/insurance scales with home price, so this is solved by bisection
    # rather than algebraically inverting the amortization formula.
    lo, hi = Decimal("0"), Decimal("5000000")
    for _ in range(60):
        mid = (lo + hi) / 2
        loan_amount = max(Decimal("0"), mid - args.down_payment)
        pi_payment = (
            calculate_amortized_payment(loan_amount, args.mortgage_rate, args.term_months)
            if loan_amount > 0
            else Decimal("0")
        )
        monthly_tax_insurance = (mid * args.property_tax_and_insurance_rate) / 12
        total_payment = pi_payment + monthly_tax_insurance
        if total_payment > max_housing_payment:
            hi = mid
        else:
            lo = mid

    max_home_price = lo.quantize(Decimal("1"))
    return {
        "max_home_price": max_home_price,
        "max_housing_payment": max_housing_payment.quantize(Decimal("0.01")),
        "max_loan_amount": (max_home_price - args.down_payment).quantize(Decimal("0.01")),
    }


class GenerateFinancialHealthScoreInput(BaseModel):
    net_worth: Decimal
    liquid_assets: Decimal
    total_liabilities: Decimal
    total_assets: Decimal
    monthly_expenses: Decimal
    target_savings_rate: Decimal
    actual_savings_rate: Decimal
    target_equity_allocation: Decimal
    actual_equity_allocation: Decimal


@registry.register(
    "generate_financial_health_score",
    "Compute a composite financial health score (0-100) with liquidity, "
    "diversification, debt-ratio, and savings-discipline sub-scores from a "
    "financial summary.",
    GenerateFinancialHealthScoreInput,
)
def generate_financial_health_score(args: GenerateFinancialHealthScoreInput):
    # Builds a minimal synthetic FinancialSnapshot from the summary figures
    # the agent already has in context, then delegates to
    # FinancialHealthService — the one place this scoring math is allowed
    # to live. Once AgentOrchestrator assembles a real FinancialSnapshot
    # from the DB (Phase 5), this synthetic construction goes away and the
    # tool takes a user_id instead of raw totals.
    from uuid import uuid4

    from app.domain.entities import Account, FinancialSnapshot, PlanningProfile, User
    from app.domain.enums import AccountType
    from app.services.financial_health_service import FinancialHealthService

    user = User(id=uuid4(), email="agent@internal", full_name="Agent Context User")
    profile = PlanningProfile(user_id=user.id)
    accounts = [
        Account(id=uuid4(), user_id=user.id, name="Liquid assets", type=AccountType.DEPOSITORY, balance=args.liquid_assets),
        Account(
            id=uuid4(), user_id=user.id, name="Other assets", type=AccountType.INVESTMENT,
            balance=max(Decimal("0"), args.total_assets - args.liquid_assets),
        ),
        Account(id=uuid4(), user_id=user.id, name="Liabilities", type=AccountType.LOAN, balance=-args.total_liabilities),
    ]
    snapshot = FinancialSnapshot(user=user, profile=profile, accounts=accounts)

    score = FinancialHealthService().score(
        snapshot,
        monthly_expenses=args.monthly_expenses,
        target_savings_rate=args.target_savings_rate,
        actual_savings_rate=args.actual_savings_rate,
        target_equity_allocation=args.target_equity_allocation,
        actual_equity_allocation=args.actual_equity_allocation,
    )
    return score
