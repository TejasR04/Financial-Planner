from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InvestmentContributionRuleCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    day_of_month: int = Field(ge=1, le=31)


class InvestmentContributionRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    amount: Decimal
    day_of_month: int
    next_run_date: date
    active: bool
    created_at: datetime
