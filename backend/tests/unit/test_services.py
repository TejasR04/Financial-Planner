from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities import (
    Account,
    FinancialSnapshot,
    IncomeSource,
    Liability,
    PlanningProfile,
    User,
)
from app.domain.enums import AccountType, DebtPayoffStrategy, FilingStatus
from app.services.cash_flow_projection_service import CashFlowProjectionService
from app.services.debt_optimization_service import DebtOptimizationService
from app.services.financial_health_service import FinancialHealthService
from app.services.net_worth_projection_service import NetWorthProjectionService
from app.services.recommendation_engine import RecommendationEngine
from app.services.retirement_projection_service import RetirementProjectionService
from app.services.tax_calculation_service import TaxCalculationService
from app.simulation.assumptions import PlanningAssumptions


# ---------- RetirementProjectionService ----------

def test_retirement_projection_grows_balance_over_time():
    service = RetirementProjectionService()
    assumptions = PlanningAssumptions(
        current_age=35,
        retirement_age=65,
        expected_return=Decimal("0.07"),
        withdrawal_rate=Decimal("0.04"),
    )
    result = service.project(
        current_retirement_balance=Decimal("200000"),
        annual_contribution=Decimal("20000"),
        assumptions=assumptions,
    )
    assert result.projected_balance_at_retirement > Decimal("200000")
    assert len(result.accumulation_series) == 30
    assert result.annual_sustainable_withdrawal == (
        result.projected_balance_at_retirement * Decimal("0.04")
    ).quantize(Decimal("0.01"))


def test_retirement_projection_feasibility_flag():
    service = RetirementProjectionService()
    assumptions = PlanningAssumptions(current_age=60, retirement_age=62, expected_return=Decimal("0.05"))
    result = service.project(
        current_retirement_balance=Decimal("100000"),
        annual_contribution=Decimal("5000"),
        assumptions=assumptions,
        annual_spending_target=Decimal("200000"),  # unreasonably high on purpose
    )
    assert result.is_feasible is False
    assert result.shortfall_or_surplus < Decimal("0")


def test_earliest_feasible_retirement_age_finds_a_reasonable_age():
    service = RetirementProjectionService()
    base = PlanningAssumptions(current_age=30, retirement_age=65, expected_return=Decimal("0.07"))
    age = service.earliest_feasible_retirement_age(
        current_retirement_balance=Decimal("50000"),
        annual_contribution=Decimal("30000"),
        base_assumptions=base,
        annual_spending_target=Decimal("40000"),
        search_to_age=70,
    )
    assert age is not None
    assert 30 < age <= 70


# ---------- NetWorthProjectionService ----------

def _sample_accounts():
    return [
        Account(id=uuid4(), user_id=uuid4(), name="Brokerage", type=AccountType.INVESTMENT, balance=Decimal("500000")),
        Account(id=uuid4(), user_id=uuid4(), name="Mortgage", type=AccountType.LOAN, balance=Decimal("-300000")),
    ]


def test_net_worth_projection_series_length_and_direction():
    service = NetWorthProjectionService()
    assumptions = PlanningAssumptions(current_age=35, retirement_age=65, expected_return=Decimal("0.07"))
    result = service.project(_sample_accounts(), assumptions, years=10, annual_net_contribution=Decimal("20000"))
    assert len(result.series) == 10
    assert result.net_worth_today == Decimal("200000")
    # assets growing + contributions + shrinking liabilities => net worth should rise
    assert result.projected_net_worth_at_horizon > result.net_worth_today


# ---------- CashFlowProjectionService ----------

def test_cash_flow_projection_basic():
    service = CashFlowProjectionService()
    income = [IncomeSource(id=uuid4(), user_id=uuid4(), name="Salary", annual_amount=Decimal("180000"), growth_rate=Decimal("0.03"))]
    result = service.project(income, monthly_expenses=Decimal("8000"), months=24)
    assert len(result.series) == 24
    assert result.series[0].income == Decimal("15000.00")
    # income should grow after 12 months due to growth_rate
    assert result.series[12].income > result.series[0].income
    assert result.projected_savings_rate > Decimal("0")


def test_cash_flow_projection_rejects_zero_months():
    service = CashFlowProjectionService()
    with pytest.raises(ValueError):
        service.project([], Decimal("1000"), months=0)


# ---------- TaxCalculationService ----------

def test_tax_estimate_includes_state_tax_for_known_state():
    service = TaxCalculationService()
    result = service.estimate(Decimal("150000"), FilingStatus.SINGLE, state="CA")
    assert result.state_tax > Decimal("0")
    assert result.total_tax > result.federal_tax


def test_tax_estimate_zero_state_tax_for_no_income_tax_state():
    service = TaxCalculationService()
    result = service.estimate(Decimal("150000"), FilingStatus.SINGLE, state="TX")
    assert result.state_tax == Decimal("0.00")


def test_roth_vs_traditional_prefers_roth_when_rate_rises():
    service = TaxCalculationService()
    result = service.calculate_roth_vs_traditional(
        annual_contribution=Decimal("10000"),
        years_to_retirement=20,
        expected_return=Decimal("0.07"),
        current_marginal_rate=Decimal("0.22"),
        expected_retirement_marginal_rate=Decimal("0.32"),
    )
    assert result.preferred == "roth"


def test_roth_vs_traditional_prefers_traditional_when_rate_falls():
    service = TaxCalculationService()
    result = service.calculate_roth_vs_traditional(
        annual_contribution=Decimal("10000"),
        years_to_retirement=20,
        expected_return=Decimal("0.07"),
        current_marginal_rate=Decimal("0.32"),
        expected_retirement_marginal_rate=Decimal("0.12"),
    )
    assert result.preferred == "traditional"


# ---------- DebtOptimizationService ----------

def test_debt_optimization_avalanche_pays_off_all_debts():
    service = DebtOptimizationService()
    liabilities = [
        Liability(id=uuid4(), account_id=uuid4(), principal=Decimal("5000"), interest_rate=Decimal("0.22"),
                   term_months=60, minimum_payment=Decimal("150"), origination_date=date(2024, 1, 1)),
        Liability(id=uuid4(), account_id=uuid4(), principal=Decimal("15000"), interest_rate=Decimal("0.06"),
                   term_months=60, minimum_payment=Decimal("300"), origination_date=date(2023, 1, 1)),
    ]
    plan = service.optimize(liabilities, extra_monthly_payment=Decimal("500"), strategy=DebtPayoffStrategy.AVALANCHE)
    assert plan.months_to_debt_free > 0
    assert len(plan.payoff_order) == 2
    # avalanche should knock out the higher-rate (22%) debt first
    assert plan.payoff_order[0] == "0"


def test_debt_optimization_snowball_pays_smallest_balance_first():
    service = DebtOptimizationService()
    liabilities = [
        Liability(id=uuid4(), account_id=uuid4(), principal=Decimal("15000"), interest_rate=Decimal("0.22"),
                   term_months=60, minimum_payment=Decimal("300"), origination_date=date(2023, 1, 1)),
        Liability(id=uuid4(), account_id=uuid4(), principal=Decimal("5000"), interest_rate=Decimal("0.06"),
                   term_months=60, minimum_payment=Decimal("150"), origination_date=date(2024, 1, 1)),
    ]
    plan = service.optimize(liabilities, extra_monthly_payment=Decimal("500"), strategy=DebtPayoffStrategy.SNOWBALL)
    assert plan.payoff_order[0] == "1"  # smaller balance, index 1


# ---------- FinancialHealthService ----------

def test_financial_health_score_within_bounds():
    service = FinancialHealthService()
    user = User(id=uuid4(), email="a@b.com", full_name="Test User", date_of_birth=date(1990, 1, 1))
    profile = PlanningProfile(user_id=user.id)
    accounts = [
        Account(id=uuid4(), user_id=user.id, name="Checking", type=AccountType.DEPOSITORY, balance=Decimal("30000")),
        Account(id=uuid4(), user_id=user.id, name="Mortgage", type=AccountType.LOAN, balance=Decimal("-100000")),
    ]
    snapshot = FinancialSnapshot(user=user, profile=profile, accounts=accounts)
    score = service.score(
        snapshot,
        monthly_expenses=Decimal("5000"),
        target_savings_rate=Decimal("0.20"),
        actual_savings_rate=Decimal("0.25"),
        target_equity_allocation=Decimal("0.60"),
        actual_equity_allocation=Decimal("0.55"),
    )
    for value in (score.overall, score.liquidity, score.diversification, score.debt_ratio, score.savings_discipline):
        assert 0 <= value <= 100


# ---------- RecommendationEngine ----------

def test_recommendation_engine_flags_idle_cash():
    engine = RecommendationEngine()
    user = User(id=uuid4(), email="a@b.com", full_name="Test User", date_of_birth=date(1990, 1, 1))
    profile = PlanningProfile(user_id=user.id)
    accounts = [
        Account(id=uuid4(), user_id=user.id, name="Checking", type=AccountType.DEPOSITORY, balance=Decimal("30000")),
        Account(id=uuid4(), user_id=user.id, name="HYSA", type=AccountType.DEPOSITORY, balance=Decimal("5000"), apy=Decimal("4.3")),
    ]
    snapshot = FinancialSnapshot(user=user, profile=profile, accounts=accounts)
    drafts = engine.generate(snapshot)
    assert any("Sweep idle cash" in d.title for d in drafts)
