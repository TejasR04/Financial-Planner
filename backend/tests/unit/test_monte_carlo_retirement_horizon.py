"""Unit tests for the retirement-horizon (decumulation) mode of
run_monte_carlo, added to replace the old accumulation-only-vs-self-
referential-target success metric.
"""
from decimal import Decimal

from app.simulation.monte_carlo import run_monte_carlo


def test_zero_volatility_survives_when_return_exceeds_withdrawal_rate():
    """With no randomness and a return safely above the withdrawal rate,
    every trial should survive the whole retirement horizon."""
    result = run_monte_carlo(
        starting_balance=Decimal("1000000"),
        annual_contribution=Decimal("0"),
        expected_return=Decimal("0.07"),
        return_volatility=Decimal("0"),
        years=0,
        starting_age=65,
        target_balance=Decimal("0"),
        retirement_years=30,
        annual_withdrawal=Decimal("40000"),  # 4% of starting balance
        trials=50,
    )
    assert result.success_rate == 1.0


def test_withdrawal_far_exceeding_balance_always_fails():
    result = run_monte_carlo(
        starting_balance=Decimal("100000"),
        annual_contribution=Decimal("0"),
        expected_return=Decimal("0.05"),
        return_volatility=Decimal("0.1"),
        years=0,
        starting_age=65,
        target_balance=Decimal("0"),
        retirement_years=30,
        annual_withdrawal=Decimal("50000"),  # 50% of balance per year — unsustainable
        trials=50,
        seed=7,
    )
    assert result.success_rate == 0.0


def test_no_retirement_years_preserves_old_accumulation_only_semantics():
    """retirement_years=0 (the default) should behave exactly as before:
    success = ending balance at the end of the accumulation phase >= target.
    """
    result = run_monte_carlo(
        starting_balance=Decimal("10000"),
        annual_contribution=Decimal("1000"),
        expected_return=Decimal("0.06"),
        return_volatility=Decimal("0"),
        years=10,
        starting_age=30,
        target_balance=Decimal("1"),  # trivially low bar
        trials=10,
    )
    assert result.success_rate == 1.0


def test_running_out_mid_retirement_clamps_to_zero_not_negative():
    result = run_monte_carlo(
        starting_balance=Decimal("50000"),
        annual_contribution=Decimal("0"),
        expected_return=Decimal("0.05"),
        return_volatility=Decimal("0.05"),
        years=0,
        starting_age=65,
        target_balance=Decimal("0"),
        retirement_years=40,
        annual_withdrawal=Decimal("20000"),
        trials=20,
        seed=3,
    )
    assert result.median_ending_balance >= Decimal("0")
    assert result.success_rate < 1.0
