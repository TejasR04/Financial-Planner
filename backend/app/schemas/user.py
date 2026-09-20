from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    base_currency: Literal["USD"]
    date_of_birth: date | None


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    base_currency: Literal["USD"] | None = None
    date_of_birth: date | None = None

    @model_validator(mode="after")
    def required_fields_cannot_be_cleared(self):
        for field in ("full_name", "base_currency"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class PlanningProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_retirement_age: int
    target_equity_allocation: Decimal
    default_withdrawal_rate: Decimal
    include_social_security: bool
    expected_return: Decimal
    inflation_rate: Decimal
    target_savings_rate: Decimal | None
    cash_reserve_target: Decimal | None


class PlanningProfileUpdateRequest(BaseModel):
    target_retirement_age: int | None = None
    target_equity_allocation: Decimal | None = None
    default_withdrawal_rate: Decimal | None = None
    include_social_security: bool | None = None
    expected_return: Decimal | None = None
    inflation_rate: Decimal | None = None
    target_savings_rate: Decimal | None = None
    cash_reserve_target: Decimal | None = None

    @model_validator(mode="after")
    def required_fields_cannot_be_cleared(self):
        nullable = {"target_savings_rate", "cash_reserve_target"}
        for field in self.model_fields_set - nullable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self
