from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.enums import GoalStatus


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    target_amount: Decimal
    target_date: date | None
    target_age: int | None
    priority: int
    status: GoalStatus
    linked_account_id: UUID | None


class GoalCreateRequest(BaseModel):
    title: str
    target_amount: Decimal
    target_date: date | None = None
    target_age: int | None = None
    priority: int = 0
    linked_account_id: UUID | None = None


class GoalUpdateRequest(BaseModel):
    title: str | None = None
    target_amount: Decimal | None = None
    target_date: date | None = None
    target_age: int | None = None
    priority: int | None = None
    status: GoalStatus | None = None
