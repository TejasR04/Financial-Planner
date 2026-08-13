from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from app.domain.enums import TransactionType


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
    budget_category_id: UUID | None = None
    transaction_type: TransactionType | None = None
    merchant_pattern: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_treatment(self):
        special = self.transaction_type in {
            TransactionType.INCOME, TransactionType.TRANSFER, TransactionType.CREDIT_CARD_PAYMENT
        }
        if (self.budget_category_id is None) == (not special):
            raise ValueError("Choose exactly one budget category, income, transfer, or credit card payment treatment")
        return self


class MerchantRuleResponse(BaseModel):
    id: UUID
    budget_category_id: UUID | None = None
    budget_category_name: str | None = None
    transaction_type: TransactionType | None = None
    merchant_pattern: str


class TransactionBudgetAssignmentRequest(BaseModel):
    budget_category_id: UUID | None = None
    ignored_from_budget: bool | None = None


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
    type: str
    budget_category_id: UUID | None = None
    budget_category_name: str | None = None
    ignored_from_budget: bool = False
