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


def project_retirement_withdrawal_series(
    starting_balance: Decimal,
    annual_withdrawal: Decimal,
    annual_rate: Decimal,
    years: int,
    starting_age: int,
    withdrawal_growth_rate: Decimal = ZERO,
) -> list[YearProjection]:
    """Project a portfolio through retirement after contributions stop.

    The withdrawal is taken at the beginning of each year and then the
    remaining balance grows for that year. In the retirement model these
    values are real dollars, so withdrawals remain level by default.
    """
    if years < 0:
        raise ValueError("years must be non-negative")
    if annual_withdrawal < ZERO:
        raise ValueError("annual_withdrawal must be non-negative")

    series: list[YearProjection] = []
    balance = starting_balance
    withdrawal = annual_withdrawal

    for i in range(years):
        amount_withdrawn = min(balance, withdrawal)
        balance_after_withdrawal = balance - amount_withdrawn
        growth = balance_after_withdrawal * annual_rate
        ending = max(ZERO, balance_after_withdrawal + growth)
        series.append(
            YearProjection(
                year_index=i + 1,
                age=starting_age + i + 1,
                starting_balance=balance,
                contributions=-amount_withdrawn,
                growth=growth,
                ending_balance=ending,
            )
        )
        balance = ending
        withdrawal = withdrawal * (ONE + withdrawal_growth_rate)

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


def inflate_to_future_dollars(amount_today: Decimal, inflation_rate: Decimal, years: int) -> Decimal:
    """Converts a today's-purchasing-power dollar amount into the nominal
    dollar amount needed `years` from now to buy the same thing, given
    `inflation_rate` compounded annually. Used to turn a user's "I want
    $X/month in today's dollars" retirement-income target into the actual
    nominal figure the plan needs to produce at retirement.
    """
    if years <= 0:
        return amount_today
    return amount_today * (Decimal("1") + inflation_rate) ** years


# Annual return standard deviation (volatility), by equity allocation
# fraction (0 = all bonds, 1 = all equities). Anchor points are real,
# cited figures rather than a single made-up constant:
#   0.19 -> 5.80%   MoneyGuidePro "Defensive" portfolio, 19% equities
#                    (via Bogleheads forum thread on MoneyGuidePro output)
#   0.405 -> 8.32%  MoneyGuidePro "Cautious" portfolio, 40.5% equities
#   0.60 -> 10.6%   Average of two independent 60/40 citations:
#                    Kitces/Tharp using 1871-2015 historical US data (11.2%),
#                    and a UK retirement Monte Carlo tool's published
#                    assumption (10%)
#   0.9425 -> 16.06% MoneyGuidePro "Aggressive" portfolio, 94.25% equities
# Piecewise-linear between these; clamped/extrapolated at the edges using
# the nearest segment's slope. This replaces a single flat volatility
# assumption that implicitly (and often wrongly) treated every user as
# holding the same 60/40-ish portfolio regardless of their actual target
# allocation.
_VOLATILITY_ANCHORS: list[tuple[Decimal, Decimal]] = [
    (Decimal("0.19"), Decimal("0.0580")),
    (Decimal("0.405"), Decimal("0.0832")),
    (Decimal("0.60"), Decimal("0.1060")),
    (Decimal("0.9425"), Decimal("0.1606")),
]


def implied_return_volatility(equity_allocation: Decimal) -> Decimal:
    """Estimated annual return standard deviation for a portfolio holding
    `equity_allocation` (0-1) in equities, the rest in bonds/cash — derived
    by interpolating between real, cited volatility figures rather than
    using one fixed number for every user regardless of their actual risk
    profile. See `_VOLATILITY_ANCHORS` for sources.
    """
    x = max(Decimal("0"), min(Decimal("1"), equity_allocation))

    if x <= _VOLATILITY_ANCHORS[0][0]:
        (x0, y0), (x1, y1) = _VOLATILITY_ANCHORS[0], _VOLATILITY_ANCHORS[1]
    elif x >= _VOLATILITY_ANCHORS[-1][0]:
        (x0, y0), (x1, y1) = _VOLATILITY_ANCHORS[-2], _VOLATILITY_ANCHORS[-1]
    else:
        (x0, y0), (x1, y1) = next(
            (lo, hi) for lo, hi in zip(_VOLATILITY_ANCHORS, _VOLATILITY_ANCHORS[1:]) if lo[0] <= x <= hi[0]
        )

    result = y0 + (x - x0) * ((y1 - y0) / (x1 - x0))
    # Guard against pathological extrapolation at extreme allocations.
    return max(Decimal("0.03"), min(Decimal("0.25"), result))
