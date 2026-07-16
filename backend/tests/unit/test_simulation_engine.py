from decimal import Decimal

import pytest

from app.domain.enums import FilingStatus
from app.simulation.engine import (
    amortize_loan,
    calculate_amortized_payment,
    compound_growth,
    contribution_limit_headroom,
    employer_match,
    estimate_federal_tax,
    future_value_of_annuity,
    inflate,
    project_balance_series,
    real_return,
    safe_withdrawal_amount,
    total_interest,
)


def test_compound_growth_basic():
    result = compound_growth(Decimal("1000"), Decimal("0.10"), 1)
    assert result == Decimal("1100.0")


def test_compound_growth_zero_years_returns_principal():
    assert compound_growth(Decimal("500"), Decimal("0.07"), 0) == Decimal("500")


def test_compound_growth_rejects_negative_years():
    with pytest.raises(ValueError):
        compound_growth(Decimal("100"), Decimal("0.05"), -1)


def test_future_value_of_annuity_matches_known_value():
    # $1000/yr at 5% for 10 years -> ~$12,577.89
    fv = future_value_of_annuity(Decimal("1000"), Decimal("0.05"), 10)
    assert abs(fv - Decimal("12577.89")) < Decimal("1")


def test_future_value_of_annuity_zero_rate_is_simple_sum():
    fv = future_value_of_annuity(Decimal("1000"), Decimal("0"), 5)
    assert fv == Decimal("5000")


def test_real_return_fisher_equation():
    r = real_return(Decimal("0.08"), Decimal("0.03"))
    expected = (Decimal("1.08") / Decimal("1.03")) - Decimal("1")
    assert r == expected
    assert r > Decimal("0.048") and r < Decimal("0.049")


def test_inflate_grows_amount_forward():
    inflated = inflate(Decimal("1000"), Decimal("0.03"), 10)
    assert inflated > Decimal("1300")
    assert inflated < Decimal("1350")


def test_project_balance_series_length_and_monotonic_growth():
    series = project_balance_series(
        starting_balance=Decimal("10000"),
        annual_contribution=Decimal("5000"),
        annual_rate=Decimal("0.07"),
        years=20,
        starting_age=30,
    )
    assert len(series) == 20
    assert series[0].age == 31
    assert series[-1].age == 50
    # every year the ending balance should exceed the starting balance
    # given a positive contribution and positive return
    for row in series:
        assert row.ending_balance > row.starting_balance
    # balances should be strictly increasing year over year
    balances = [row.ending_balance for row in series]
    assert balances == sorted(balances)


def test_project_balance_series_zero_years_returns_empty():
    assert project_balance_series(Decimal("100"), Decimal("10"), Decimal("0.05"), 0, 30) == []


def test_amortize_loan_pays_off_to_zero():
    schedule = amortize_loan(Decimal("300000"), Decimal("0.065"), 360)
    assert len(schedule) == 360
    assert schedule[-1].remaining_balance == Decimal("0.00")
    # every row's balance should be non-increasing
    balances = [row.remaining_balance for row in schedule]
    assert balances == sorted(balances, reverse=True)


def test_amortize_loan_total_interest_is_positive_and_reasonable():
    schedule = amortize_loan(Decimal("300000"), Decimal("0.065"), 360)
    interest = total_interest(schedule)
    # a 30yr 6.5% loan on 300k should generate more interest than principal
    assert interest > Decimal("300000")


def test_calculate_amortized_payment_zero_rate():
    payment = calculate_amortized_payment(Decimal("12000"), Decimal("0"), 12)
    assert payment == Decimal("1000.00")


def test_employer_match_caps_at_match_cap_rate():
    # 100% match up to 4% of a $100k salary; employee contributes 10%
    match = employer_match(
        salary=Decimal("100000"),
        employee_contribution_rate=Decimal("0.10"),
        match_rate=Decimal("1.0"),
        match_cap_rate=Decimal("0.04"),
    )
    assert match == Decimal("4000")


def test_employer_match_below_cap_matches_full_contribution():
    match = employer_match(
        salary=Decimal("100000"),
        employee_contribution_rate=Decimal("0.02"),
        match_rate=Decimal("0.5"),
        match_cap_rate=Decimal("0.04"),
    )
    assert match == Decimal("1000")  # 0.5 * min(2000, 4000)


def test_contribution_limit_headroom_under_limit():
    result = contribution_limit_headroom(Decimal("10000"), "401k_employee", age=35)
    assert result["limit"] == Decimal("23500")
    assert result["headroom"] == Decimal("13500")
    assert result["over_limit"] is False


def test_contribution_limit_headroom_catchup_applies_at_50():
    result = contribution_limit_headroom(Decimal("23500"), "401k_employee", age=52)
    assert result["limit"] == Decimal("31000")
    assert result["over_limit"] is False


def test_contribution_limit_headroom_over_limit():
    result = contribution_limit_headroom(Decimal("30000"), "401k_employee", age=35)
    assert result["over_limit"] is True


def test_estimate_federal_tax_zero_income_is_zero_tax():
    result = estimate_federal_tax(Decimal("0"), FilingStatus.SINGLE)
    assert result["total_tax"] == Decimal("0")


def test_estimate_federal_tax_progressive_brackets_single():
    # $100,000 single filer, 2025 brackets, standard deduction
    result = estimate_federal_tax(Decimal("100000"), FilingStatus.SINGLE)
    assert result["taxable_income"] == Decimal("85000")
    assert result["total_tax"] > Decimal("0")
    assert result["marginal_rate"] == Decimal("0.22")
    # effective rate should always be below the marginal rate in a progressive system
    assert result["effective_rate"] < result["marginal_rate"]


def test_estimate_federal_tax_higher_income_higher_marginal_rate():
    low = estimate_federal_tax(Decimal("50000"), FilingStatus.SINGLE)
    high = estimate_federal_tax(Decimal("500000"), FilingStatus.SINGLE)
    assert high["marginal_rate"] > low["marginal_rate"]
    assert high["total_tax"] > low["total_tax"]


def test_safe_withdrawal_amount():
    assert safe_withdrawal_amount(Decimal("1000000"), Decimal("0.04")) == Decimal("40000.00")
