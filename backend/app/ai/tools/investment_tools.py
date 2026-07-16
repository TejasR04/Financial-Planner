from decimal import Decimal

from pydantic import BaseModel

from app.ai.tool_registry import registry
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
