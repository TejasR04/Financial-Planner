from decimal import Decimal

from pydantic import BaseModel

from app.ai.tool_registry import registry
from app.simulation.monte_carlo import run_monte_carlo as _run_monte_carlo


class RunMonteCarloInput(BaseModel):
    starting_balance: Decimal
    annual_contribution: Decimal
    expected_return: Decimal = Decimal("0.065")
    return_volatility: Decimal = Decimal("0.15")
    years: int
    current_age: int
    target_balance: Decimal
    trials: int = 1000


@registry.register(
    "run_monte_carlo",
    "Run a Monte Carlo simulation of portfolio growth under randomized "
    "annual returns and report the probability of reaching a target "
    "balance by a given horizon.",
    RunMonteCarloInput,
)
def run_monte_carlo(args: RunMonteCarloInput):
    result = _run_monte_carlo(
        starting_balance=args.starting_balance,
        annual_contribution=args.annual_contribution,
        expected_return=args.expected_return,
        return_volatility=args.return_volatility,
        years=args.years,
        starting_age=args.current_age,
        target_balance=args.target_balance,
        trials=args.trials,
    )
    return result


class OptimizeMonthlySurplusInput(BaseModel):
    monthly_surplus: Decimal
    has_high_interest_debt: bool
    retirement_contribution_headroom: Decimal
    emergency_fund_gap: Decimal = Decimal("0")


@registry.register(
    "optimize_monthly_surplus",
    "Recommend how to allocate a monthly cash surplus across an emergency "
    "fund, high-interest debt payoff, and retirement contributions, "
    "following a standard priority order.",
    OptimizeMonthlySurplusInput,
)
def optimize_monthly_surplus(args: OptimizeMonthlySurplusInput):
    remaining = args.monthly_surplus
    allocation: dict[str, Decimal] = {}

    if args.emergency_fund_gap > 0:
        to_emergency_fund = min(remaining, args.emergency_fund_gap)
        allocation["emergency_fund"] = to_emergency_fund
        remaining -= to_emergency_fund

    if args.has_high_interest_debt and remaining > 0:
        # Priority: high-interest debt beats retirement contributions once
        # a baseline emergency fund exists — standard personal-finance
        # ordering, not a computed optimization (see DebtOptimizationService
        # for the actual payoff schedule once a debt amount is known).
        to_debt = remaining
        allocation["high_interest_debt"] = to_debt
        remaining -= to_debt
    elif remaining > 0:
        to_retirement = min(remaining, args.retirement_contribution_headroom)
        allocation["retirement"] = to_retirement
        remaining -= to_retirement

    if remaining > 0:
        allocation["taxable_investing"] = remaining

    return {"monthly_surplus": args.monthly_surplus, "allocation": allocation}
