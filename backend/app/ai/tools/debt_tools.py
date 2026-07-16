from datetime import date
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel

from app.ai.tool_registry import registry
from app.domain.entities import Liability
from app.domain.enums import DebtPayoffStrategy
from app.services.debt_optimization_service import DebtOptimizationService

_debt_service = DebtOptimizationService()


class LiabilityInput(BaseModel):
    name: str
    principal: Decimal
    interest_rate: Decimal
    minimum_payment: Decimal
    term_months: int = 360


class PrioritizeDebtPayoffInput(BaseModel):
    liabilities: list[LiabilityInput]
    extra_monthly_payment: Decimal
    strategy: DebtPayoffStrategy = DebtPayoffStrategy.AVALANCHE


@registry.register(
    "prioritize_debt_payoff",
    "Build a debt payoff plan (avalanche = highest interest first, "
    "snowball = smallest balance first) given a list of debts and an "
    "extra monthly payment amount.",
    PrioritizeDebtPayoffInput,
)
def prioritize_debt_payoff(args: PrioritizeDebtPayoffInput):
    liabilities = [
        Liability(
            id=uuid4(),
            account_id=uuid4(),
            principal=item.principal,
            interest_rate=item.interest_rate,
            term_months=item.term_months,
            minimum_payment=item.minimum_payment,
            origination_date=date.today(),
        )
        for item in args.liabilities
    ]
    plan = _debt_service.optimize(
        liabilities=liabilities,
        extra_monthly_payment=args.extra_monthly_payment,
        strategy=args.strategy,
    )
    # Map back to the caller's debt names for a readable tool result.
    name_by_index = {str(i): item.name for i, item in enumerate(args.liabilities)}
    return {
        "strategy": plan.strategy.value,
        "months_to_debt_free": plan.months_to_debt_free,
        "total_interest_paid": plan.total_interest_paid,
        "payoff_order": [name_by_index[i] for i in plan.payoff_order],
    }
