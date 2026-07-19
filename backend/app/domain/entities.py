"""Framework-free domain entities.

These are the objects business services operate on. They know nothing about
SQLAlchemy or FastAPI. Persistence maps ORM rows to/from these; the API
layer maps these to/from Pydantic schemas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.domain.enums import (
    AccountStatus,
    AccountType,
    AssetClass,
    GoalStatus,
    InsightKind,
    InstitutionStatus,
    ProviderType,
    RecommendationEffort,
    RecommendationStatus,
    TransactionStatus,
    TransactionType,
)


@dataclass(slots=True)
class User:
    id: UUID
    email: str
    full_name: str
    base_currency: str = "USD"
    date_of_birth: date | None = None

    def age_on(self, as_of: date) -> int | None:
        if self.date_of_birth is None:
            return None
        years = as_of.year - self.date_of_birth.year
        if (as_of.month, as_of.day) < (self.date_of_birth.month, self.date_of_birth.day):
            years -= 1
        return years


@dataclass(slots=True)
class PlanningProfile:
    user_id: UUID
    target_retirement_age: int = 65
    target_equity_allocation: Decimal = Decimal("0.60")
    default_withdrawal_rate: Decimal = Decimal("0.04")
    include_social_security: bool = True
    expected_return: Decimal = Decimal("0.065")
    inflation_rate: Decimal = Decimal("0.028")


@dataclass(slots=True)
class Institution:
    id: UUID
    user_id: UUID
    name: str
    provider: ProviderType
    status: InstitutionStatus = InstitutionStatus.HEALTHY
    last_synced_at: datetime | None = None
    external_item_id: str | None = None


@dataclass(slots=True)
class Account:
    id: UUID
    user_id: UUID
    name: str
    type: AccountType
    balance: Decimal
    currency: str = "USD"
    institution_id: UUID | None = None
    mask: str | None = None
    apy: Decimal | None = None
    status: AccountStatus = AccountStatus.MANUAL
    updated_at: datetime | None = None
    external_account_id: str | None = None

    @property
    def is_liability(self) -> bool:
        return self.type in (AccountType.CREDIT, AccountType.LOAN) or self.balance < 0


@dataclass(slots=True)
class Holding:
    id: UUID
    account_id: UUID
    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    market_value: Decimal
    asset_class: AssetClass
    as_of: date


@dataclass(slots=True)
class Transaction:
    id: UUID
    account_id: UUID
    posted_at: date
    merchant: str
    category: str
    amount: Decimal
    type: TransactionType
    status: TransactionStatus = TransactionStatus.CLEARED


@dataclass(slots=True)
class IncomeSource:
    id: UUID
    user_id: UUID
    name: str
    annual_amount: Decimal
    growth_rate: Decimal = Decimal("0.03")
    active: bool = True


@dataclass(slots=True)
class Liability:
    id: UUID
    account_id: UUID
    principal: Decimal
    interest_rate: Decimal
    term_months: int
    minimum_payment: Decimal
    origination_date: date


@dataclass(slots=True)
class Goal:
    id: UUID
    user_id: UUID
    title: str
    target_amount: Decimal
    target_date: date | None = None
    target_age: int | None = None
    priority: int = 0
    status: GoalStatus = GoalStatus.UPCOMING
    linked_account_id: UUID | None = None


@dataclass(slots=True)
class Recommendation:
    id: UUID
    user_id: UUID
    title: str
    body: str
    category: str
    impact_value: Decimal
    effort: RecommendationEffort
    confidence: float
    status: RecommendationStatus = RecommendationStatus.NEW
    generated_at: datetime | None = None


@dataclass(slots=True)
class Insight:
    id: UUID
    user_id: UUID
    kind: InsightKind
    text: str
    meta: str
    generated_at: datetime | None = None


@dataclass(slots=True)
class FinancialSnapshot:
    """Everything a service needs to compute a projection or recommendation,
    assembled once per request so services never touch the DB themselves."""
    user: User
    profile: PlanningProfile
    accounts: list[Account] = field(default_factory=list)
    holdings: list[Holding] = field(default_factory=list)
    liabilities: list[Liability] = field(default_factory=list)
    income_sources: list[IncomeSource] = field(default_factory=list)
    goals: list[Goal] = field(default_factory=list)
    as_of: date = field(default_factory=date.today)

    @property
    def net_worth(self) -> Decimal:
        return sum((a.balance for a in self.accounts), Decimal("0"))

    @property
    def liquid_assets(self) -> Decimal:
        from app.domain.enums import AccountType as AT
        return sum(
            (a.balance for a in self.accounts if a.type == AT.DEPOSITORY and a.balance > 0),
            Decimal("0"),
        )
