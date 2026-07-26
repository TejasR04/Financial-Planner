from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class BudgetCategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    group_name: str = Field(default="Other", min_length=1, max_length=100)
    monthly_limit: Decimal = Field(ge=0)


class BudgetCategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    group_name: str | None = Field(default=None, min_length=1, max_length=100)
    monthly_limit: Decimal | None = Field(default=None, ge=0)
    active: bool | None = None


class BudgetCategoryResponse(BaseModel):
    id: UUID
    name: str
    group_name: str
    monthly_limit: Decimal
    sort_order: int
    active: bool


class MerchantRuleCreateRequest(BaseModel):
    budget_category_id: UUID
    merchant_pattern: str = Field(min_length=1, max_length=255)


class MerchantRuleResponse(BaseModel):
    id: UUID
    budget_category_id: UUID
    budget_category_name: str
    merchant_pattern: str


class TransactionBudgetAssignmentRequest(BaseModel):
    budget_category_id: UUID | None = None


class BudgetCategorySummaryResponse(BaseModel):
    budget_category_id: UUID
    name: str
    group_name: str
    budgeted: Decimal
    spent: Decimal
    pending: Decimal
    remaining: Decimal
    forecast: Decimal


class UncategorizedSpendResponse(BaseModel):
    spent: Decimal
    pending: Decimal
    transaction_count: int


class BudgetSummaryResponse(BaseModel):
    month: date
    categories: list[BudgetCategorySummaryResponse]
    uncategorized: UncategorizedSpendResponse


class UncategorizedTransactionResponse(BaseModel):
    id: UUID
    posted_at: date
    merchant: str
    provider_category: str
    amount: Decimal
    status: str
