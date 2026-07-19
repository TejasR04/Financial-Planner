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
from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal("0")


@dataclass(slots=True, frozen=True)
class MonteCarloResult:
    trials: int
    success_rate: float          # meaning depends on mode — see run_monte_carlo docstring
    median_ending_balance: Decimal
    p10_ending_balance: Decimal
    p90_ending_balance: Decimal
    seed: int


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
      `annual_withdrawal` at the start of each year (then growing the
      remainder at that year's sampled return — the standard
      sequence-of-returns convention). `success_rate` here means the
      fraction of trials that never hit a zero balance before the end of
      that retirement horizon — i.e. "didn't run out of money" — which is
      what `ScenarioService` uses so "success rate" answers the question
      people actually mean by it for a retirement scenario. `target_balance`
      is ignored in this mode.

    Simplification worth knowing: `annual_withdrawal` is held flat in
    nominal terms across the retirement horizon (not inflation-adjusted
    year over year, unlike the classic real-terms "4% rule"). Fine for a
    v1; a future pass could index it to `inflation_rate` per year.

    This is deliberately simple (normal, i.i.d. annual returns) — a
    reasonable default for a v1 that is explicitly designed to be replaced
    (bootstrapped historical sequences, fatter tails) without touching any
    caller.
    """
    if trials <= 0:
        raise ValueError("trials must be positive")

    rng = random.Random(seed)
    endings: list[Decimal] = []
    successes = 0

    mean = float(expected_return)
    stdev = float(return_volatility)

    for _ in range(trials):
        balance = starting_balance
        contribution = annual_contribution
        for _year in range(years):
            sampled_rate = Decimal(str(rng.normalvariate(mean, stdev)))
            balance = balance + contribution + balance * sampled_rate
            if balance < ZERO:
                balance = ZERO

        ran_out = False
        for _year in range(retirement_years):
            sampled_rate = Decimal(str(rng.normalvariate(mean, stdev)))
            balance = balance - annual_withdrawal
            if balance <= ZERO:
                balance = ZERO
                ran_out = True
                continue
            balance = balance * (Decimal("1") + sampled_rate)
            if balance < ZERO:
                balance = ZERO

        endings.append(balance)
        if retirement_years > 0:
            if not ran_out:
                successes += 1
        elif balance >= target_balance:
            successes += 1

    endings_sorted = sorted(endings)
    n = len(endings_sorted)
    median = endings_sorted[n // 2]
    p10 = endings_sorted[max(0, int(n * 0.10) - 1)]
    p90 = endings_sorted[min(n - 1, int(n * 0.90))]

    return MonteCarloResult(
        trials=trials,
        success_rate=successes / trials,
        median_ending_balance=median,
        p10_ending_balance=p10,
        p90_ending_balance=p90,
        seed=seed,
    )