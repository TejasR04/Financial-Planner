from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class FinancialHealthScoreResponse(BaseModel):
    overall: int
    liquidity: int
    diversification: int
    debt_ratio: int
    savings_discipline: int
    calculated_at: datetime | None = None


class FinancialHealthRecalculateRequest(BaseModel):
    """All fields optional: omitted values fall back to snapshot-derived
    defaults (see the route docstring for exactly what each default is).
    Provide them explicitly whenever the caller has better data than the
    backend can currently infer — e.g. an actual monthly expense figure
    from a budgeting flow the frontend hasn't built yet.
    """
    monthly_expenses: Decimal | None = None
    target_savings_rate: Decimal | None = None
    actual_savings_rate: Decimal | None = None


class AllocationBreakdownResponse(BaseModel):
    asset_class: str
    market_value: Decimal
    weight: Decimal


class RebalanceSuggestionResponse(BaseModel):
    asset_class: str
    action: str
    amount: Decimal


class AllocationAnalysisResponse(BaseModel):
    total_market_value: Decimal
    breakdown: list[AllocationBreakdownResponse]
    actual_equity_allocation: Decimal
    target_equity_allocation: Decimal
    drift: Decimal
    is_within_tolerance: bool
    rebalance_suggestions: list[RebalanceSuggestionResponse]
