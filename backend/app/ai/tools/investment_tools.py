from decimal import Decimal

from pydantic import BaseModel

from app.ai.tool_registry import registry
from app.domain.enums import AssetClass
from app.simulation.engine import contribution_limit_headroom, employer_match


class Calculate401kMatchInput(BaseModel):
    salary: Decimal
    employee_contribution_rate: Decimal
    employer_match_rate: Decimal
    employer_match_cap_rate: Decimal
    age: int = 30


@registry.register(
    "calculate_401k_match",
    "Calculate the annual employer 401(k) match given a salary, employee "
    "contribution rate, and the employer's match formula, and check the "
    "result against the current-year IRS contribution limit.",
    Calculate401kMatchInput,
)
def calculate_401k_match(args: Calculate401kMatchInput):
    match = employer_match(
        salary=args.salary,
        employee_contribution_rate=args.employee_contribution_rate,
        match_rate=args.employer_match_rate,
        match_cap_rate=args.employer_match_cap_rate,
    )
    employee_contribution = args.salary * args.employee_contribution_rate
    headroom = contribution_limit_headroom(employee_contribution, "401k_employee", args.age)
    return {
        "annual_employer_match": match,
        "annual_employee_contribution": employee_contribution,
        "irs_limit_headroom": headroom["headroom"],
        "over_irs_limit": headroom["over_limit"],
    }


class HoldingInput(BaseModel):
    symbol: str
    market_value: Decimal
    asset_class: AssetClass


class AnalyzeAllocationInput(BaseModel):
    holdings: list[HoldingInput]
    target_equity_allocation: Decimal


@registry.register(
    "analyze_allocation",
    "Analyze a portfolio's actual asset allocation against a target equity "
    "allocation and suggest rebalancing trades if the drift exceeds a "
    "reasonable tolerance.",
    AnalyzeAllocationInput,
)
def analyze_allocation(args: AnalyzeAllocationInput):
    from datetime import date
    from uuid import uuid4

    from app.domain.entities import Holding
    from app.services.portfolio_allocation_service import PortfolioAllocationService

    holdings = [
        Holding(
            id=uuid4(), account_id=uuid4(), symbol=h.symbol, quantity=Decimal("0"),
            cost_basis=h.market_value, market_value=h.market_value, asset_class=h.asset_class, as_of=date.today(),
        )
        for h in args.holdings
    ]
    return PortfolioAllocationService().analyze(holdings, args.target_equity_allocation)
