"""Persistence models for read-only reporting, agent credentials, and audit history."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.session import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AgentTokenModel(Base):
    __tablename__ = "agent_tokens"
    __table_args__ = (Index("ix_agent_tokens_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    token_prefix: Mapped[str] = mapped_column(String(16))
    scopes: Mapped[list[str]] = mapped_column(JSONB, default=lambda: ["reports:read"])
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReportingEnrollmentModel(Base):
    __tablename__ = "reporting_enrollments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FinancialReportModel(Base):
    __tablename__ = "financial_reports"
    __table_args__ = (
        Index(
            "uq_financial_reports_daily_user_date",
            "user_id",
            "scheduled_date",
            unique=True,
            postgresql_where=text("is_baseline = false"),
        ),
        Index(
            "uq_financial_reports_baseline_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_baseline = true"),
        ),
        Index("ix_financial_reports_user_captured", "user_id", "captured_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scheduled_date: Mapped[date] = mapped_column(Date, index=True)
    is_baseline: Mapped[bool] = mapped_column(default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    previous_report_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("financial_reports.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class FinancialChangeEventModel(Base):
    __tablename__ = "financial_change_events"
    __table_args__ = (
        Index("ix_financial_change_events_unassigned", "user_id", "observed_at", postgresql_where=text("report_id IS NULL")),
        Index("ix_financial_change_events_report", "report_id", "observed_at"),
        Index("ix_financial_change_events_entity", "entity_type", "entity_id", "observed_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(12))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    source: Mapped[str] = mapped_column(String(40), default="unknown")
    before_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("financial_reports.id", ondelete="SET NULL"), nullable=True, index=True
    )


class FinancialSyncRunModel(Base):
    __tablename__ = "financial_sync_runs"
    __table_args__ = (Index("ix_financial_sync_runs_user_finished", "user_id", "finished_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

