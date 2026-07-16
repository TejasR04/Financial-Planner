"""The deterministic simulation engine.

Every function here is pure: given the same inputs it always returns the
same output, no I/O, no randomness (Monte Carlo sampling is layered on top
in `monte_carlo.py` by repeatedly calling `project_balance_series` with
sampled returns — this module stays the single source of truth for the math
itself).

All money math uses Decimal. All rates are decimals (0.065, not 6.5).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import FilingStatus
from app.simulation import tax_tables

TWO = Decimal("2")
ONE = Decimal("1")
ZERO = Decimal("0")
MONTHS_PER_YEAR = 12


def annual_rate_to_monthly(annual_rate: Decimal) -> Decimal:
    """Effective monthly rate compounding to the given effective annual rate."""
    return (ONE + annual_rate) ** (Decimal("1") / Decimal(MONTHS_PER_YEAR)) - ONE


def compound_growth(principal: Decimal, annual_rate: Decimal, years: int) -> Decimal:
    """Future value of a lump sum compounded annually for `years` years."""
    if years < 0:
        raise ValueError("years must be non-negative")
    return principal * (ONE + annual_rate) ** years


def future_value_of_annuity(
    contribution_per_period: Decimal, rate_per_period: Decimal, periods: int
) -> Decimal:
    """Future value of a level series of end-of-period contributions
    (ordinary annuity). Used for annual salary contributions and monthly
    account contributions alike — caller picks the period."""
    if periods < 0:
        raise ValueError("periods must be non-negative")
    if periods == 0:
        return ZERO
    if rate_per_period == ZERO:
        return contribution_per_period * periods
    return contribution_per_period * (((ONE + rate_per_period) ** periods - ONE) / rate_per_period)


def inflate(amount: Decimal, inflation_rate: Decimal, years: int) -> Decimal:
    """Nominal amount required in `years` years to match today's purchasing
    power of `amount`."""
    return compound_growth(amount, inflation_rate, years)


def real_return(nominal_rate: Decimal, inflation_rate: Decimal) -> Decimal:
    """Fisher equation: inflation-adjusted rate of return."""
    return (ONE + nominal_rate) / (ONE + inflation_rate) - ONE


@dataclass(slots=True, frozen=True)
class YearProjection:
    year_index: int
    age: int
    starting_balance: Decimal
    contributions: Decimal
    growth: Decimal
    ending_balance: Decimal


def project_balance_series(
    starting_balance: Decimal,
    annual_contribution: Decimal,
    annual_rate: Decimal,
    years: int,
    starting_age: int,
    contribution_growth_rate: Decimal = ZERO,
) -> list[YearProjection]:
    """Year-by-year balance projection with annual compounding and an
    optional annually-growing contribution (e.g. salary growth carried into
    savings). Contributions are applied at year-end, then growth is applied
    to the balance including that year's contribution — i.e. growth compounds
    on top of contributions made during the year at a simplifying
    mid/end-of-year convention appropriate for multi-decade planning
    horizons (not day-level accuracy).
    """
    if years < 0:
        raise ValueError("years must be non-negative")

    series: list[YearProjection] = []
    balance = starting_balance
    contribution = annual_contribution

    for i in range(years):
        growth = balance * annual_rate
        ending = balance + contribution + growth
        series.append(
            YearProjection(
                year_index=i + 1,
                age=starting_age + i + 1,
                starting_balance=balance,
                contributions=contribution,
                growth=growth,
                ending_balance=ending,
            )
        )
        balance = ending
        contribution = contribution * (ONE + contribution_growth_rate)

    return series


@dataclass(slots=True, frozen=True)
class AmortizationRow:
    period: int
    payment: Decimal
    principal_paid: Decimal
    interest_paid: Decimal
    remaining_balance: Decimal


def amortize_loan(
    principal: Decimal, annual_interest_rate: Decimal, term_months: int
) -> list[AmortizationRow]:
    """Standard fixed-rate, fixed-term amortization schedule."""
    if principal <= ZERO:
        raise ValueError("principal must be positive")
    if term_months <= 0:
        raise ValueError("term_months must be positive")

    monthly_rate = annual_interest_rate / Decimal(MONTHS_PER_YEAR)
    payment = calculate_amortized_payment(principal, annual_interest_rate, term_months)

    schedule: list[AmortizationRow] = []
    balance = principal
    for period in range(1, term_months + 1):
        interest = (balance * monthly_rate).quantize(Decimal("0.01"))
        principal_paid = payment - interest
        if period == term_months:
            # true up the final payment to zero out any rounding drift
            principal_paid = balance
            payment_final = principal_paid + interest
            balance = ZERO
            schedule.append(
                AmortizationRow(period, payment_final.quantize(Decimal("0.01")), principal_paid, interest, balance)
            )
            break
        balance = balance - principal_paid
        schedule.append(
            AmortizationRow(period, payment.quantize(Decimal("0.01")), principal_paid, interest, balance)
        )
    return schedule


def calculate_amortized_payment(
    principal: Decimal, annual_interest_rate: Decimal, term_months: int
) -> Decimal:
    """Standard fixed-payment formula. Returns the level monthly payment."""
    if annual_interest_rate == ZERO:
        return (principal / term_months).quantize(Decimal("0.01"))
    monthly_rate = annual_interest_rate / Decimal(MONTHS_PER_YEAR)
    factor = (ONE + monthly_rate) ** term_months
    payment = principal * (monthly_rate * factor) / (factor - ONE)
    return payment.quantize(Decimal("0.01"))


def total_interest(schedule: list[AmortizationRow]) -> Decimal:
    return sum((row.interest_paid for row in schedule), ZERO)


def employer_match(
    salary: Decimal, employee_contribution_rate: Decimal, match_rate: Decimal, match_cap_rate: Decimal
) -> Decimal:
    """Employer 401(k) match: `match_rate` matched on employee contributions,
    up to `match_cap_rate` of salary. E.g. "100% match up to 4% of salary"
    is match_rate=1.0, match_cap_rate=0.04.
    """
    if salary < ZERO:
        raise ValueError("salary must be non-negative")
    employee_contribution = salary * employee_contribution_rate
    matchable_contribution = min(employee_contribution, salary * match_cap_rate)
    return matchable_contribution * match_rate


def contribution_limit_headroom(
    planned_annual_contribution: Decimal, limit_key: str, age: int, tax_year: int = tax_tables.DEFAULT_TAX_YEAR
) -> dict[str, Decimal]:
    """Compares a planned contribution against the IRS limit for the given
    account type, including the age-50+ catch-up where applicable.
    `limit_key` is one of the keys in `tax_tables.get_contribution_limits`
    (e.g. "401k_employee", "ira", "hsa_individual").
    """
    limits = tax_tables.get_contribution_limits(tax_year)
    base_limit = limits[limit_key]
    catchup_key = f"{limit_key}_catchup_50plus"
    catchup = limits.get(catchup_key, ZERO) if age >= 50 else ZERO
    effective_limit = base_limit + catchup
    headroom = effective_limit - planned_annual_contribution
    return {
        "limit": effective_limit,
        "planned": planned_annual_contribution,
        "headroom": headroom,
        "over_limit": headroom < ZERO,
    }


def estimate_federal_tax(
    taxable_income_before_deduction: Decimal,
    filing_status: FilingStatus,
    tax_year: int = tax_tables.DEFAULT_TAX_YEAR,
    itemized_deduction: Decimal | None = None,
) -> dict[str, Decimal]:
    """Progressive marginal-bracket federal income tax estimate. Applies the
    greater of the standard deduction or a provided itemized deduction, then
    walks the bracket table. Returns total tax, effective rate, and marginal
    rate — this is an estimate for planning, not a filing calculation (no
    credits, no AMT, no state tax — see TaxCalculationService for state).
    """
    standard_deduction = tax_tables.get_standard_deduction(tax_year, filing_status)
    deduction = max(standard_deduction, itemized_deduction or ZERO)
    taxable_income = max(ZERO, taxable_income_before_deduction - deduction)

    brackets = tax_tables.get_brackets(tax_year, filing_status)
    tax = ZERO
    lower = ZERO
    marginal_rate = ZERO
    for upper, rate in brackets:
        if upper is None or taxable_income <= upper:
            tax += (taxable_income - lower) * rate
            marginal_rate = rate
            break
        tax += (upper - lower) * rate
        lower = upper

    tax = tax.quantize(Decimal("0.01"))
    effective_rate = (tax / taxable_income_before_deduction) if taxable_income_before_deduction > ZERO else ZERO
    return {
        "taxable_income": taxable_income,
        "deduction_applied": deduction,
        "total_tax": tax,
        "effective_rate": effective_rate.quantize(Decimal("0.0001")),
        "marginal_rate": marginal_rate,
    }


def safe_withdrawal_amount(portfolio_balance: Decimal, withdrawal_rate: Decimal) -> Decimal:
    """Annual sustainable withdrawal under a fixed-rate rule (e.g. the 4%
    rule). A thin, explicit wrapper kept separate from RetirementProjectionService
    so it can also be used directly as an AI tool primitive."""
    return portfolio_balance * withdrawal_rate
