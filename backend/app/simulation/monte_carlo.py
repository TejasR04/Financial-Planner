"""Monte Carlo layer on top of the deterministic engine.

Phase 7 in the roadmap calls for a "real" sampler (e.g. bootstrapped
historical returns, fat-tailed distributions). This module ships a minimal
normal-distribution sampler now so `simulation_runs.method = monte_carlo` is
wired end to end; swapping the sampler later requires no change to
`RetirementProjectionService` or any API contract, since both only see
`MonteCarloResult`.
"""
from __future__ import annotations

import random
import math
from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal("0")
MODEL_VERSION = "normal-iid-monthly-contributions-v3"
PERCENTILE_METHOD = "nearest-rank"


@dataclass(slots=True, frozen=True)
class MonteCarloResult:
    trials: int
    success_rate: float          # meaning depends on mode — see run_monte_carlo docstring
    median_ending_balance: Decimal
    p10_ending_balance: Decimal
    p90_ending_balance: Decimal
    seed: int
    success_metric: str
    model_version: str = MODEL_VERSION
    percentile_method: str = PERCENTILE_METHOD


def run_monte_carlo(
    starting_balance: Decimal,
    annual_contribution: Decimal,
    expected_return: Decimal,
    return_volatility: Decimal,
    years: int,
    starting_age: int,
    target_balance: Decimal,
    trials: int = 1000,
    seed: int = 42,
    retirement_years: int = 0,
    annual_withdrawal: Decimal = ZERO,
    annual_withdrawal_growth_rate: Decimal = ZERO,
    annual_fee_rate: Decimal = ZERO,
) -> MonteCarloResult:
    """Runs `trials` independent projections with the annual return sampled
    from a normal distribution around `expected_return`.

    Two modes, selected by whether `retirement_years > 0`:

    - **Accumulation-only (`retirement_years=0`, the default)**: simulates
      `years` of contributions + random growth and reports the fraction of
      trials whose ENDING balance is >= `target_balance`. This is what
      backs the generic `/simulations/monte-carlo` endpoint and the
      `run_monte_carlo` AI tool, where there's no retirement horizon to
      model — just "does this savings plan clear this bar".

    - **Full retirement horizon (`retirement_years > 0`)**: after the same
      `years` of accumulation, each trial continues for `retirement_years`
      more years with NO further contributions, instead withdrawing
      `annual_withdrawal` at the start of the first retirement year, then
      growing that withdrawal by `annual_withdrawal_growth_rate` each
      subsequent year (pass the plan's inflation rate here to hold
      purchasing power constant — the standard "real spending" retirement
      model — or 0 to hold it flat in nominal dollars). The remaining
      balance grows at that year's sampled return (the standard
      sequence-of-returns convention). `success_rate` here means the
      fraction of trials that never hit a zero balance before the end of
      that retirement horizon — i.e. "didn't run out of money" — which is
      what `ScenarioService` uses so "success rate" answers the question
      people actually mean by it for a retirement scenario. `target_balance`
      is ignored in this mode.

    This is deliberately simple (normal, i.i.d. annual returns) — a
    reasonable default for a v1 that is explicitly designed to be replaced
    (bootstrapped historical sequences, fatter tails) without touching any
    caller.
    """
    if not 100 <= trials <= 100_000:
        raise ValueError("trials must be between 100 and 100000")
    if not 0 <= years <= 100 or not 0 <= retirement_years <= 100:
        raise ValueError("projection horizons must be between 0 and 100 years")
    if not 0 <= starting_age <= 120 or starting_age + years + retirement_years > 130:
        raise ValueError("ages and combined horizon are outside supported bounds")
    if starting_balance < ZERO or annual_contribution < ZERO or target_balance < ZERO:
        raise ValueError("balances and contributions cannot be negative")
    if annual_withdrawal < ZERO:
        raise ValueError("annual_withdrawal cannot be negative")
    if not Decimal("-0.50") <= expected_return <= Decimal("0.50"):
        raise ValueError("expected_return must be between -0.50 and 0.50")
    if not ZERO <= return_volatility <= Decimal("1.00"):
        raise ValueError("return_volatility must be between 0 and 1")
    if not ZERO <= annual_fee_rate < Decimal("1.00"):
        raise ValueError("annual_fee_rate must be between 0 and 1")
    if not Decimal("-0.20") <= annual_withdrawal_growth_rate <= Decimal("0.20"):
        raise ValueError("annual_withdrawal_growth_rate must be between -0.20 and 0.20")

    rng = random.Random(seed)
    endings: list[Decimal] = []
    successes = 0

    mean = float(expected_return)
    stdev = float(return_volatility)
    growth_factor = Decimal("1") + annual_withdrawal_growth_rate
    monthly_contribution = annual_contribution / Decimal("12")

    for _ in range(trials):
        balance = starting_balance
        for _year in range(years):
            sampled_rate = Decimal(str(rng.normalvariate(mean, stdev)))
            net_annual_factor = max(
                ZERO,
                (Decimal("1") + sampled_rate) * (Decimal("1") - annual_fee_rate),
            )
            monthly_factor = net_annual_factor ** (Decimal("1") / Decimal("12"))
            for _month in range(12):
                balance = balance * monthly_factor + monthly_contribution

        ran_out = False
        withdrawal = annual_withdrawal
        for _year in range(retirement_years):
            sampled_rate = Decimal(str(rng.normalvariate(mean, stdev)))
            balance = balance - withdrawal
            if balance <= ZERO:
                balance = ZERO
                ran_out = True
            else:
                balance = balance * max(
                    ZERO,
                    (Decimal("1") + sampled_rate) * (Decimal("1") - annual_fee_rate),
                )
                if balance < ZERO:
                    balance = ZERO
            withdrawal = withdrawal * growth_factor

        endings.append(balance)
        if retirement_years > 0:
            if not ran_out:
                successes += 1
        elif balance >= target_balance:
            successes += 1

    endings_sorted = sorted(endings)
    n = len(endings_sorted)
    def nearest_rank(percentile: Decimal) -> Decimal:
        return endings_sorted[max(0, math.ceil(float(percentile) * n) - 1)]
    median = nearest_rank(Decimal("0.50"))
    p10 = nearest_rank(Decimal("0.10"))
    p90 = nearest_rank(Decimal("0.90"))

    return MonteCarloResult(
        trials=trials,
        success_rate=successes / trials,
        median_ending_balance=median,
        p10_ending_balance=p10,
        p90_ending_balance=p90,
        seed=seed,
        success_metric="retirement_survival" if retirement_years > 0 else "target_attainment",
    )
