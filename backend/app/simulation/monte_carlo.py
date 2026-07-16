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
import statistics
from dataclasses import dataclass
from decimal import Decimal

from app.simulation.engine import project_balance_series

ZERO = Decimal("0")


@dataclass(slots=True, frozen=True)
class MonteCarloResult:
    trials: int
    success_rate: float          # fraction of trials meeting the target
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
) -> MonteCarloResult:
    """Runs `trials` independent projections with the annual return sampled
    from a normal distribution around `expected_return`, and reports the
    fraction of trials that end at or above `target_balance`.

    This is deliberately simple (normal, i.i.d. annual returns) — a
    reasonable default for a v1 that is explicitly designed to be replaced
    (bootstrapped historical sequences, fatter tails, sequence-of-returns
    risk) without touching any caller.
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
        endings.append(balance)
        if balance >= target_balance:
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
