from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from app.domain.merchant_rules import normalize_merchant_rule

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoanBalanceRuleCreate(BaseModel):
    mode: Literal["scheduled", "merchant"]
    amount: Decimal | None = Field(default=None, gt=0)
    frequency: Literal["once", "monthly"] | None = None
    next_run_date: date | None = None
    merchant_pattern: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def valid_configuration(self):
        if self.mode == "scheduled":
            if self.amount is None or self.frequency is None or self.next_run_date is None:
                raise ValueError("Scheduled payments require an amount, frequency, and first payment date.")
            self.merchant_pattern = None
        else:
            pattern = normalize_merchant_rule(self.merchant_pattern or "", collapse_transfers=False)
            if len(pattern) < 2:
                raise ValueError("Enter at least two characters from the merchant name.")
            self.merchant_pattern = pattern
            self.amount = None
            self.frequency = None
            self.next_run_date = None
        return self


class LoanBalanceRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    mode: Literal["scheduled", "merchant"]
    amount: Decimal | None
    frequency: Literal["once", "monthly"] | None
    next_run_date: date | None
    merchant_pattern: str | None
    active: bool
    created_at: datetime
