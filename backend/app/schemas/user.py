from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    base_currency: str
    date_of_birth: date | None


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    base_currency: str | None = None
    date_of_birth: date | None = None


class PlanningProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_retirement_age: int
    target_equity_allocation: Decimal
    default_withdrawal_rate: Decimal
    include_social_security: bool
    expected_return: Decimal
    inflation_rate: Decimal


class PlanningProfileUpdateRequest(BaseModel):
    target_retirement_age: int | None = None
    target_equity_allocation: Decimal | None = None
    default_withdrawal_rate: Decimal | None = None
    include_social_security: bool | None = None
    expected_return: Decimal | None = None
    inflation_rate: Decimal | None = None
