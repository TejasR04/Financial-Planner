"""SQLAlchemy ORM models. This is the only file in the codebase that should
import sqlalchemy.orm mapping constructs — everything else works with
`app.domain.entities` dataclasses. Repositories translate between the two.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.session import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    base_currency: Mapped[str] = mapped_column(String(3), default="USD")
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    profile: Mapped["PlanningProfileModel"] = relationship(back_populates="user", uselist=False)
    accounts: Mapped[list["AccountModel"]] = relationship(back_populates="user")


class PlanningProfileModel(Base):
    __tablename__ = "planning_profiles"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    target_retirement_age: Mapped[int] = mapped_column(Integer, default=65)
    target_equity_allocation: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.60"))
    default_withdrawal_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.04"))
    include_social_security: Mapped[bool] = mapped_column(Boolean, default=True)
    expected_return: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.065"))
    inflation_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.028"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    user: Mapped["UserModel"] = relationship(back_populates="profile")


class InstitutionModel(Base):
    __tablename__ = "institutions"
    __table_args__ = (UniqueConstraint("external_item_id", name="uq_institutions_external_item_id"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="healthy")
    external_item_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Plaid access_token, Fernet-encrypted (see app/core/crypto.py). Never
    # decrypted outside PlaidProvider, never included in any API schema.
    plaid_access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Cursor for Plaid's /transactions/sync (Phase B). Stored now since the
    # column lives on the same row Phase A already creates.
    plaid_sync_cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AccountModel(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), index=True)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(20))
    mask: Mapped[str | None] = mapped_column(String(8), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    apy: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="manual")
    external_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    user: Mapped["UserModel"] = relationship(back_populates="accounts")
    holdings: Mapped[list["HoldingModel"]] = relationship(back_populates="account")
    liability: Mapped["LiabilityModel"] = relationship(back_populates="account", uselist=False)


class HoldingModel(Base):
    __tablename__ = "holdings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("accounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    asset_class: Mapped[str] = mapped_column(String(20))
    as_of: Mapped[date] = mapped_column(Date)

    account: Mapped["AccountModel"] = relationship(back_populates="holdings")


class TransactionModel(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("accounts.id"), index=True)
    posted_at: Mapped[date] = mapped_column(Date, index=True)
    merchant: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="cleared")
    external_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class IncomeSourceModel(Base):
    __tablename__ = "income_sources"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    annual_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    growth_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.03"))
    type: Mapped[str] = mapped_column(String(20), default="salary")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class LiabilityModel(Base):
    __tablename__ = "liabilities"

    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("accounts.id"), unique=True)
    principal: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    term_months: Mapped[int] = mapped_column(Integer)
    minimum_payment: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    origination_date: Mapped[date] = mapped_column(Date)

    account: Mapped["AccountModel"] = relationship(back_populates="liability")


class GoalModel(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    target_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="upcoming")
    linked_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )


class ScenarioModel(Base):
    __tablename__ = "scenarios"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    retirement_age: Mapped[int] = mapped_column(Integer)
    savings_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    monthly_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    expected_return: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    inflation_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    withdrawal_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    runs: Mapped[list["SimulationRunModel"]] = relationship(back_populates="scenario")


class SimulationRunModel(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    scenario_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scenarios.id"), index=True)
    engine_version: Mapped[str] = mapped_column(String(20))
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    method: Mapped[str] = mapped_column(String(20), default="deterministic")
    net_worth_at_target_age: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    monthly_sustainable_withdrawal: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    success_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    trajectory: Mapped[dict] = mapped_column(JSONB)
    assumptions_snapshot: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    scenario: Mapped["ScenarioModel"] = relationship(back_populates="runs")


class RecommendationModel(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100))
    impact_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    effort: Mapped[str] = mapped_column(String(10))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3))
    status: Mapped[str] = mapped_column(String(20), default="new")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("simulation_runs.id"), nullable=True
    )


class InsightModel(Base):
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    meta: Mapped[str] = mapped_column(String(255))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FinancialHealthScoreModel(Base):
    __tablename__ = "financial_health_scores"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), index=True)
    overall: Mapped[int] = mapped_column(Integer)
    liquidity: Mapped[int] = mapped_column(Integer)
    diversification: Mapped[int] = mapped_column(Integer)
    debt_ratio: Mapped[int] = mapped_column(Integer)
    savings_discipline: Mapped[int] = mapped_column(Integer)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)