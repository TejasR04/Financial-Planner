"""Capture and serve immutable, read-only financial reports."""
from __future__ import annotations

import asyncio
import base64
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.financial_date import financial_today
from app.domain.category_mapping import match_existing_category
from app.domain.merchant_rules import merchant_matches_rule
from app.domain.report_comparison import compare_report_states
from app.persistence.models import (
    AccountModel,
    BudgetCategoryModel,
    HoldingModel,
    InstitutionModel,
    InvestmentContributionAdjustmentModel,
    IncomeSourceModel,
    LiabilityModel,
    MerchantBudgetRuleModel,
    TransactionModel,
    UserModel,
)
from app.persistence.reporting_models import (
    FinancialChangeEventModel,
    FinancialReportModel,
    FinancialSyncRunModel,
    ReportingEnrollmentModel,
)
from app.persistence.session import AsyncSessionLocal, engine
from app.services.budget_service import BudgetCategoryInput, BudgetService, BudgetTransactionInput

logger = logging.getLogger("meridian.daily_reports")
ZERO = Decimal("0")
REPORT_SCHEMA_VERSION = 1
PAGE_SIZE_MAX = 200


def _iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _decimal(value: Decimal | int | float | None) -> str:
    return format(Decimal(value or 0), "f")


def _money(value: Decimal | int | float | None) -> str:
    return format(Decimal(value or 0).quantize(Decimal("0.01")), "f")


async def _load_snapshot(
    db: AsyncSession, user_id: UUID, captured_at: datetime, *, as_of: date | None = None,
) -> dict[str, Any]:
    """Read source tables directly; reporting must not call mutating GET routes."""
    today = as_of or captured_at.astimezone(ZoneInfo(get_settings().financial_timezone)).date()
    month = today.replace(day=1)
    user = await db.get(UserModel, user_id)
    currency = user.base_currency if user else "USD"

    accounts: list[AccountModel] = list((await db.scalars(
        select(AccountModel).where(AccountModel.user_id == user_id, AccountModel.archived_at.is_(None))
        .order_by(AccountModel.id)
    )).all())
    institutions: list[InstitutionModel] = list((await db.scalars(select(InstitutionModel).where(InstitutionModel.user_id == user_id))).all())
    institutions_by_id = {row.id: row for row in institutions}
    holdings: list[HoldingModel] = list((await db.scalars(
        select(HoldingModel).join(AccountModel, AccountModel.id == HoldingModel.account_id)
        .where(AccountModel.user_id == user_id, AccountModel.archived_at.is_(None))
        .order_by(HoldingModel.id)
    )).all())

    account_items = []
    asset_total = liability_total = ZERO
    investment_accounts = []
    investment_types = {"investment", "retirement"}
    liability_types = {"credit", "loan"}
    for row in accounts:
        amount = Decimal(row.balance or 0)
        is_liability = row.type in liability_types
        if is_liability:
            liability_total += abs(amount)
        else:
            asset_total += amount
        institution = institutions_by_id.get(row.institution_id) if row.institution_id is not None else None
        item = {
            "id": str(row.id), "name": row.custom_name or row.name, "type": row.type,
            "balance": _money(amount), "currency": row.currency,
            "updated_at": _iso(row.updated_at), "institution": institution.name if institution else None,
            "archived": False,
        }
        account_items.append(item)
        if row.type in investment_types:
            investment_accounts.append(item)

    account_names = {str(row.id): row.custom_name or row.name for row in accounts}
    liabilities = list((await db.scalars(
        select(LiabilityModel).join(AccountModel, AccountModel.id == LiabilityModel.account_id)
        .where(AccountModel.user_id == user_id, AccountModel.archived_at.is_(None))
        .order_by(LiabilityModel.account_id)
    )).all())
    liability_details = [
        {
            "account_id": str(row.account_id), "account_name": account_names.get(str(row.account_id), ""),
            "account_balance": _money(next((account.balance for account in accounts if account.id == row.account_id), ZERO)),
            "principal": _money(row.principal) if row.principal is not None else None,
            "interest_rate": _decimal(row.interest_rate) if row.interest_rate is not None else None,
            "term_months": row.term_months,
            "minimum_payment": _money(row.minimum_payment) if row.minimum_payment is not None else None,
            "origination_date": row.origination_date.isoformat() if row.origination_date else None,
            "last_interest_accrual_date": row.last_interest_accrual_date.isoformat()
            if row.last_interest_accrual_date else None,
        }
        for row in liabilities
    ]
    income_sources = list((await db.scalars(
        select(IncomeSourceModel).where(IncomeSourceModel.user_id == user_id)
        .order_by(IncomeSourceModel.id)
    )).all())
    income_details = [
        {
            "id": str(row.id), "name": row.name, "annual_amount": _money(row.annual_amount),
            "growth_rate": _decimal(row.growth_rate), "type": row.type, "active": row.active,
        }
        for row in income_sources
    ]
    holding_items = [
        {
            "id": str(row.id), "account_id": str(row.account_id),
            "account_name": account_names.get(str(row.account_id), ""), "symbol": row.symbol,
            "quantity": _decimal(row.quantity), "cost_basis": _money(row.cost_basis),
            "market_value": _money(row.market_value), "asset_class": row.asset_class,
            "as_of": row.as_of.isoformat(), "last_price": _decimal(row.last_price) if row.last_price is not None else None,
        }
        for row in holdings
    ]
    investment_account_ids = {row.id for row in accounts if row.type in investment_types}
    investment_holdings = [item for item in holding_items if item["account_id"] in {str(value) for value in investment_account_ids}]
    investment_value = sum((Decimal(str(row["balance"])) for row in investment_accounts), ZERO)
    investment_holdings_value = sum((Decimal(str(row["market_value"])) for row in investment_holdings), ZERO)

    categories = list((await db.scalars(
        select(BudgetCategoryModel).where(BudgetCategoryModel.user_id == user_id)
        .order_by(BudgetCategoryModel.sort_order, BudgetCategoryModel.name)
    )).all())
    rules = list((await db.scalars(
        select(MerchantBudgetRuleModel).where(MerchantBudgetRuleModel.user_id == user_id)
        .order_by(MerchantBudgetRuleModel.created_at)
    )).all())
    month_transactions: list[TransactionModel] = list((await db.scalars(
        select(TransactionModel).join(AccountModel, AccountModel.id == TransactionModel.account_id)
        .where(
            AccountModel.user_id == user_id,
            TransactionModel.deleted_at.is_(None),
            TransactionModel.posted_at >= month,
            TransactionModel.posted_at <= today,
        )
    )).all())
    active_categories = [(row.id, row.name) for row in categories if row.active]
    active_category_ids = {row.id for row in categories if row.active}
    budget_transactions: list[BudgetTransactionInput] = []
    for transaction in month_transactions:
        category_id = transaction.budget_category_id if transaction.budget_category_id in active_category_ids else None
        transaction_type = transaction.type
        if category_id is None and transaction.reviewed_at is None:
            matching_rule = next((rule for rule in rules if merchant_matches_rule(transaction.merchant, rule.merchant_pattern)), None)
            rule_applied = False
            if matching_rule is not None:
                if matching_rule.budget_category_id in active_category_ids:
                    category_id = matching_rule.budget_category_id
                    if transaction_type not in {"expense", "transfer"}:
                        transaction_type = "expense"
                    rule_applied = True
                elif matching_rule.transaction_type:
                    transaction_type = matching_rule.transaction_type
                    rule_applied = True
            if not rule_applied and transaction_type == "expense" and not transaction.ignored_from_budget:
                category_id = match_existing_category(transaction.category, active_categories)
        budget_transactions.append(BudgetTransactionInput(
            merchant=transaction.merchant, amount=Decimal(transaction.amount), status=transaction.status,
            budget_category_id=category_id, type=transaction_type,
            ignored_from_budget=transaction.ignored_from_budget, provider_category=transaction.category,
            posted_at=transaction.posted_at, reviewed_at=transaction.reviewed_at,
        ))
    service = BudgetService()
    rollups, uncategorized_spent, uncategorized_pending, uncategorized_count = service.summarize(
        [BudgetCategoryInput(row.id, row.name, row.group_name, Decimal(row.monthly_limit), row.active) for row in categories],
        [],
        budget_transactions,
        month,
        today,
    )
    rollup_by_id = {row.budget_category_id: row for row in rollups}
    budget_categories = []
    for category in categories:
        rollup = rollup_by_id.get(category.id)
        budget_categories.append({
            "id": str(category.id), "name": category.name, "group_name": category.group_name,
            "monthly_limit": _money(category.monthly_limit), "active": category.active,
            "spent": _money(rollup.spent if rollup else ZERO),
            "pending": _money(rollup.pending if rollup else ZERO),
            "remaining": _money(rollup.remaining if rollup else Decimal(category.monthly_limit)),
            "forecast": _money(rollup.forecast if rollup else ZERO),
        })

    contribution_sum = await db.scalar(
        select(func.coalesce(func.sum(InvestmentContributionAdjustmentModel.amount), 0))
        .where(
            InvestmentContributionAdjustmentModel.account_id.in_(investment_account_ids)
            if investment_account_ids else text("false"),
            InvestmentContributionAdjustmentModel.scheduled_for >= month,
            InvestmentContributionAdjustmentModel.scheduled_for <= today,
            InvestmentContributionAdjustmentModel.holdings_applied.is_(True),
        )
    )
    contribution_transactions = sum(
        (Decimal(row.amount) for row in month_transactions if row.type == "contribution"), ZERO
    )

    sync_runs = list((await db.scalars(
        select(FinancialSyncRunModel).where(FinancialSyncRunModel.user_id == user_id)
        .order_by(FinancialSyncRunModel.started_at.desc()).limit(10)
    )).all())
    latest_sync = sync_runs[0] if sync_runs else None
    recent_sync_attempts = [
        {
            "id": str(row.id), "source": row.source, "status": row.status,
            "started_at": _iso(row.started_at), "finished_at": _iso(row.finished_at),
            "errors": row.error_summary or {},
        }
        for row in sync_runs
    ]
    freshness_warnings: list[dict[str, str]] = []
    institution_status = []
    for institution in institutions:
        if institution.provider != "plaid":
            continue
        last_synced = institution.last_synced_at
        stale = last_synced is None or (captured_at - last_synced).total_seconds() > 24 * 60 * 60
        item = {
            "id": str(institution.id), "name": institution.custom_name or institution.name,
            "status": institution.status, "last_synced_at": _iso(last_synced), "stale": stale,
        }
        institution_status.append(item)
        if stale:
            freshness_warnings.append({"code": "institution_sync_stale", "message": f"{item['name']} has not synced successfully in the last 24 hours."})
        if institution.status in {"error", "action_required"}:
            freshness_warnings.append({"code": "institution_needs_attention", "message": f"{item['name']} is marked {institution.status}."})
    if latest_sync and latest_sync.status in {"failed", "partial"}:
        freshness_warnings.append({
            "code": "latest_sync_incomplete", "message": "The latest financial refresh did not complete cleanly.",
        })
    if latest_sync and latest_sync.status == "running":
        stale_run = (captured_at - latest_sync.started_at).total_seconds() > 15 * 60
        freshness_warnings.append({
            "code": "sync_run_stale" if stale_run else "sync_running",
            "message": "The latest financial refresh has been running for more than 15 minutes." if stale_run
            else "A financial refresh is still running.",
        })
    stale_holdings = [holding for holding in investment_holdings if str(holding["as_of"]) < today.isoformat()]
    if stale_holdings:
        freshness_warnings.append({"code": "investment_quotes_stale", "message": f"{len(stale_holdings)} investment position(s) have a quote date before the report date."})

    latest_sync_data = None
    if latest_sync:
        latest_sync_data = {
            "id": str(latest_sync.id), "source": latest_sync.source, "status": latest_sync.status,
            "started_at": _iso(latest_sync.started_at), "finished_at": _iso(latest_sync.finished_at),
            "errors": latest_sync.error_summary or {},
        }

    return {
        "currency": currency,
        "summary": {
            "currency": currency, "assets": _money(asset_total), "liabilities": _money(liability_total),
            "net_worth": _money(asset_total - liability_total), "account_count": len(accounts),
            "asset_account_count": sum(1 for row in accounts if row.type not in liability_types),
            "liability_account_count": sum(1 for row in accounts if row.type in liability_types),
        },
        "accounts": account_items,
        "liability_details": liability_details,
        "income_sources": income_details,
        "reporting_timezone": get_settings().financial_timezone,
        "investments": {
            "account_value": _money(investment_value), "holdings_value": _money(investment_holdings_value),
            "contribution_transactions_mtd": _money(contribution_transactions),
            "scheduled_rule_adjustments_mtd": _money(Decimal(contribution_sum or 0)),
            "accounts": investment_accounts, "holdings": investment_holdings,
        },
        "budgets": {
            "month": month.isoformat(), "categories": budget_categories,
            "uncategorized": {
                "spent": _money(uncategorized_spent), "pending": _money(uncategorized_pending),
                "transaction_count": uncategorized_count,
            },
        },
        "freshness": {
            "captured_at": captured_at.isoformat(), "institutions": institution_status,
            "latest_sync": latest_sync_data, "recent_sync_attempts": recent_sync_attempts,
            "warnings": freshness_warnings,
        },
    }


def _event_data(row: FinancialChangeEventModel) -> dict[str, Any]:
    return {
        "id": str(row.id), "entity_type": row.entity_type, "entity_id": row.entity_id,
        "operation": row.operation, "observed_at": _iso(row.observed_at), "source": row.source,
        "identity_transition": row.source == "identity_transition",
        "before": row.before_values, "after": row.after_values,
    }


async def enable_reporting(db: AsyncSession, user_id: UUID) -> None:
    """Enroll a user and create a separate immutable comparison baseline.

    This helper only flushes. Callers own the surrounding transaction.
    """
    # Serialize concurrent first-time token creation for the same owner before
    # checking for an enrollment or baseline. The advisory lock below also
    # serializes this transaction with report capture.
    owner_id = await db.scalar(
        select(UserModel.id).where(UserModel.id == user_id).with_for_update()
    )
    if owner_id is None:
        raise ValueError("Cannot enable reporting for an unknown user")
    # Share the capture lock so creating a first baseline cannot interleave
    # with an in-flight daily capture for the same user.
    await db.execute(text(
        "SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"
    ), {"lock_key": f"meridian:daily-report:{user_id}"})
    enrollment = await db.get(ReportingEnrollmentModel, user_id)
    if enrollment is None:
        db.add(ReportingEnrollmentModel(user_id=user_id))
        await db.flush()
    baseline = await db.scalar(select(FinancialReportModel).where(
        FinancialReportModel.user_id == user_id, FinancialReportModel.is_baseline.is_(True)
    ))
    if baseline is not None:
        return
    captured_at = datetime.now(timezone.utc)
    # The credential transaction already began during authentication. Read
    # both baseline state and eligible events in a separate consistent view,
    # while enrollment and the credential still commit atomically below.
    source_engine = cast(AsyncEngine, db.bind or engine)
    baseline_factory = async_sessionmaker(
        bind=source_engine.execution_options(isolation_level="REPEATABLE READ"),
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with baseline_factory() as reader:
        async with reader.begin():
            baseline_event_ids = list((await reader.scalars(select(FinancialChangeEventModel.id).where(
                FinancialChangeEventModel.user_id == user_id,
                FinancialChangeEventModel.report_id.is_(None),
            ))).all())
            snapshot = await _load_snapshot(reader, user_id, captured_at, as_of=financial_today())
    baseline = FinancialReportModel(
        user_id=user_id, scheduled_date=financial_today(), is_baseline=True, status="ready",
        started_at=captured_at, completed_at=captured_at, captured_at=captured_at,
        schema_version=REPORT_SCHEMA_VERSION, snapshot=snapshot,
    )
    db.add(baseline)
    await db.flush()
    if baseline_event_ids:
        await db.execute(update(FinancialChangeEventModel).where(
            FinancialChangeEventModel.id.in_(baseline_event_ids),
            FinancialChangeEventModel.report_id.is_(None),
        ).values(report_id=baseline.id))
    await db.flush()


async def enabled_reporting_users(db: AsyncSession) -> list[UUID]:
    result = await db.scalars(
        select(ReportingEnrollmentModel.user_id)
        .join(UserModel, UserModel.id == ReportingEnrollmentModel.user_id)
        .where(UserModel.archived_at.is_(None))
        .order_by(ReportingEnrollmentModel.user_id)
    )
    return list(result.all())


async def record_sync_run_started(db: AsyncSession, user_id: UUID, source: str) -> UUID:
    run = FinancialSyncRunModel(user_id=user_id, source=source, status="running")
    db.add(run)
    await db.flush()
    return run.id


async def finish_sync_run(
    db: AsyncSession, run_id: UUID, status: str, error_summary: dict[str, Any] | None = None,
) -> None:
    run = await db.get(FinancialSyncRunModel, run_id)
    if run is None:
        return
    run.status = status if status in {"succeeded", "partial", "failed"} else "failed"
    run.finished_at = datetime.now(timezone.utc)
    run.error_summary = error_summary or None
    await db.flush()


def _to_report_dict(report: FinancialReportModel, previous: FinancialReportModel | None = None) -> dict[str, Any]:
    if report.status != "ready":
        return {
            "status": report.status, "report_id": str(report.id),
            "date": report.scheduled_date.isoformat(), "captured_at": _iso(report.captured_at),
            "error": report.failure_message,
        }
    data = report.snapshot or {}
    return {
        "status": "ready", "report_id": str(report.id), "date": report.scheduled_date.isoformat(),
        "captured_at": _iso(report.captured_at), "previous_report_id": str(report.previous_report_id) if report.previous_report_id else None,
        "reporting_window": {
            "from": _iso(previous.captured_at) if previous else None,
            "to": _iso(report.captured_at),
            "description": "Since the previous completed capture" if previous else "Baseline capture; no earlier report is available.",
        },
        **data,
    }


async def capture_daily_report(user_id: UUID, report_date: date | None = None) -> dict[str, Any]:
    """Capture one user under a PostgreSQL advisory lock; retries are idempotent."""
    report_date = report_date or financial_today()
    lock_key = f"meridian:daily-report:{user_id}"
    bind = engine
    lock_connection = await bind.connect()
    lock_connection = await lock_connection.execution_options(isolation_level="AUTOCOMMIT")
    locked = False
    try:
        await lock_connection.execute(text("SELECT pg_advisory_lock(hashtextextended(:lock_key, 0))"), {"lock_key": lock_key})
        locked = True
        capture_factory = async_sessionmaker(
            bind=engine.execution_options(isolation_level="REPEATABLE READ"),
            expire_on_commit=False,
            class_=AsyncSession,
        )
        async with capture_factory() as db:
            async with db.begin():
                report = await db.scalar(select(FinancialReportModel).where(
                    FinancialReportModel.user_id == user_id,
                    FinancialReportModel.scheduled_date == report_date,
                    FinancialReportModel.is_baseline.is_(False),
                ))
                if report and report.status == "ready":
                    previous = await db.get(FinancialReportModel, report.previous_report_id) if report.previous_report_id else None
                    return _to_report_dict(report, previous)
                if report is None:
                    report = FinancialReportModel(
                        user_id=user_id, scheduled_date=report_date, is_baseline=False,
                        status="pending", started_at=datetime.now(timezone.utc),
                    )
                    db.add(report)
                else:
                    report.status = "pending"
                    report.started_at = datetime.now(timezone.utc)
                    report.failure_message = None
                await db.flush()
                report_id = report.id

            try:
                async with db.begin():
                    report = await db.scalar(select(FinancialReportModel).where(
                        FinancialReportModel.id == report_id,
                        FinancialReportModel.user_id == user_id,
                    ).with_for_update())
                    if report is None:
                        raise RuntimeError("Daily report capture record disappeared")
                    if report.status == "ready":
                        previous = await db.get(FinancialReportModel, report.previous_report_id) if report.previous_report_id else None
                        return _to_report_dict(report, previous)
                    captured_at = datetime.now(timezone.utc)
                    snapshot = await _load_snapshot(db, user_id, captured_at, as_of=report_date)
                    previous = await db.scalar(
                        select(FinancialReportModel)
                        .where(
                            FinancialReportModel.user_id == user_id,
                            FinancialReportModel.status == "ready",
                            FinancialReportModel.captured_at.is_not(None),
                            FinancialReportModel.id != report.id,
                            FinancialReportModel.captured_at <= captured_at,
                        )
                        .order_by(FinancialReportModel.captured_at.desc())
                        .limit(1)
                    )
                    event_rows = list((await db.scalars(
                        select(FinancialChangeEventModel)
                        .where(
                            FinancialChangeEventModel.user_id == user_id,
                            FinancialChangeEventModel.report_id.is_(None),
                            FinancialChangeEventModel.observed_at <= captured_at,
                        )
                        .order_by(FinancialChangeEventModel.observed_at, FinancialChangeEventModel.id)
                    )).all())
                    event_items = [_event_data(row) for row in event_rows]
                    transaction_events = [item for item in event_items if item["entity_type"] == "transactions"]
                    snapshot["changes"] = compare_report_states(
                        previous.snapshot if previous else None, snapshot, transaction_events[:100]
                    )
                    snapshot["changes"]["transaction_event_count"] = len(transaction_events)
                    snapshot["changes"]["audited_event_count"] = len(event_items)
                    snapshot["changes"]["event_counts_by_entity"] = {
                        entity: sum(1 for item in event_items if item["entity_type"] == entity)
                        for entity in sorted({item["entity_type"] for item in event_items})
                    }
                    snapshot["changes"]["audited_event_preview"] = event_items[:100]
                    report.previous_report_id = previous.id if previous else None
                    report.snapshot = snapshot
                    report.schema_version = REPORT_SCHEMA_VERSION
                    report.captured_at = captured_at
                    report.completed_at = datetime.now(timezone.utc)
                    report.status = "ready"
                    report.failure_message = None
                    if event_rows:
                        await db.execute(update(FinancialChangeEventModel).where(
                            FinancialChangeEventModel.id.in_([row.id for row in event_rows]),
                            FinancialChangeEventModel.report_id.is_(None),
                        ).values(report_id=report.id))
                    await db.flush()
                    return _to_report_dict(report, previous)
            except Exception as exc:
                # Exception strings can contain SQL parameters and financial
                # values. Keep diagnostics useful without copying those into
                # the durable report or logs.
                logger.error(
                    "daily_report_capture_failed",
                    extra={
                        "user_id": str(user_id),
                        "date": report_date.isoformat(),
                        "error_type": type(exc).__name__,
                    },
                )
                public_error = "Report capture failed. Please retry or contact support."
                async with db.begin():
                    report = await db.scalar(select(FinancialReportModel).where(
                        FinancialReportModel.id == report_id,
                        FinancialReportModel.user_id == user_id,
                    ).with_for_update())
                    if report is not None:
                        report.status = "failed"
                        report.failure_message = public_error
                        report.completed_at = datetime.now(timezone.utc)
                    await db.flush()
                return {
                    "status": "failed", "report_id": str(report_id), "date": report_date.isoformat(),
                    "error": public_error,
                }
    finally:
        if locked:
            await lock_connection.execute(text("SELECT pg_advisory_unlock(hashtextextended(:lock_key, 0))"), {"lock_key": lock_key})
        await lock_connection.close()


async def mark_daily_report_failed(user_id: UUID, report_date: date, message: str) -> None:
    """Persist scheduler-level failures such as an unavailable sync lease."""
    async with AsyncSessionLocal() as db:
        async with db.begin():
            report = await db.scalar(select(FinancialReportModel).where(
                FinancialReportModel.user_id == user_id,
                FinancialReportModel.scheduled_date == report_date,
                FinancialReportModel.is_baseline.is_(False),
            ).with_for_update())
            if report is not None and report.status == "ready":
                return
            if report is None:
                report = FinancialReportModel(
                    user_id=user_id, scheduled_date=report_date, is_baseline=False,
                    status="failed", started_at=datetime.now(timezone.utc),
                )
                db.add(report)
            report.status = "failed"
            report.completed_at = datetime.now(timezone.utc)
            report.failure_message = message[:1000]
            await db.flush()


async def get_current_summary(db: AsyncSession, user_id: UUID) -> dict[str, Any]:
    captured_at = datetime.now(timezone.utc)
    # Authentication may already have used the request session, so capture the
    # current view in a fresh repeatable-read transaction instead of attempting
    # to change that transaction's isolation level after it has started.
    source_engine = cast(AsyncEngine, db.bind or engine)
    read_factory = async_sessionmaker(
        bind=source_engine.execution_options(isolation_level="REPEATABLE READ"),
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with read_factory() as reader:
        async with reader.begin():
            snapshot = await _load_snapshot(reader, user_id, captured_at)
    return {"captured_at": captured_at.isoformat(), **snapshot}


async def get_daily_report(
    db: AsyncSession, user_id: UUID, report_date: date, wait_seconds: int = 0,
) -> dict[str, Any]:
    wait_seconds = max(0, min(30, int(wait_seconds)))
    deadline = asyncio.get_running_loop().time() + wait_seconds
    while True:
        report = await db.scalar(select(FinancialReportModel).where(
            FinancialReportModel.user_id == user_id,
            FinancialReportModel.scheduled_date == report_date,
            FinancialReportModel.is_baseline.is_(False),
        ))
        if report is not None:
            if report.status == "ready":
                previous = await db.get(FinancialReportModel, report.previous_report_id) if report.previous_report_id else None
                return _to_report_dict(report, previous)
            if report.status == "failed" and (
                wait_seconds == 0 or asyncio.get_running_loop().time() >= deadline
            ):
                return _to_report_dict(report)
        else:
            enrolled = await db.get(ReportingEnrollmentModel, user_id)
            if enrolled is None:
                return {"status": "unavailable", "date": report_date.isoformat(), "error": "Reporting is not enabled for this user."}
        if asyncio.get_running_loop().time() >= deadline:
            if report is not None and report.status == "failed":
                return _to_report_dict(report)
            return {
                "status": "pending", "report_id": str(report.id) if report else None,
                "date": report_date.isoformat(), "captured_at": None,
                "message": "The report capture has not completed yet.",
            }
        await db.rollback()
        await asyncio.sleep(min(2, max(0.1, deadline - asyncio.get_running_loop().time())))


def _cursor_encode(observed_at: datetime, event_id: UUID) -> str:
    raw = f"{observed_at.isoformat()}|{event_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _cursor_decode(cursor: str | None) -> tuple[datetime, UUID] | None:
    if not cursor:
        return None
    if len(cursor) > 256:
        raise ValueError("Cursor is too long")
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        timestamp, identifier = raw.split("|", 1)
        return datetime.fromisoformat(timestamp), UUID(identifier)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid pagination cursor") from exc


async def list_reports(
    db: AsyncSession, user_id: UUID, start_date: date | None = None,
    end_date: date | None = None, cursor: str | None = None, limit: int = 50,
) -> dict[str, Any]:
    limit = max(1, min(PAGE_SIZE_MAX, int(limit)))
    decoded = _cursor_decode(cursor)
    query = select(FinancialReportModel).where(
        FinancialReportModel.user_id == user_id,
        FinancialReportModel.is_baseline.is_(False),
    )
    if start_date:
        query = query.where(FinancialReportModel.scheduled_date >= start_date)
    if end_date:
        query = query.where(FinancialReportModel.scheduled_date <= end_date)
    if decoded:
        cursor_time, cursor_id = decoded
        query = query.where(
            (FinancialReportModel.started_at < cursor_time)
            | ((FinancialReportModel.started_at == cursor_time) & (FinancialReportModel.id < cursor_id))
        )
    rows = list((await db.scalars(query.order_by(
        FinancialReportModel.started_at.desc(), FinancialReportModel.id.desc()
    ).limit(limit + 1))).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    previous_ids = [row.previous_report_id for row in rows if row.previous_report_id is not None]
    previous_rows = list((await db.scalars(select(FinancialReportModel).where(
        FinancialReportModel.user_id == user_id,
        FinancialReportModel.id.in_(previous_ids) if previous_ids else text("false"),
    ))).all())
    previous_by_id = {row.id: row for row in previous_rows}
    items = [
        _to_report_dict(
            row,
            previous_by_id.get(row.previous_report_id) if row.previous_report_id is not None else None,
        )
        for row in rows
    ]
    next_cursor = _cursor_encode(rows[-1].started_at, rows[-1].id) if has_more and rows else None
    return {"items": items, "next_cursor": next_cursor}


async def get_report_changes(
    db: AsyncSession, user_id: UUID, report_id: UUID, cursor: str | None = None, limit: int = 100,
) -> dict[str, Any]:
    limit = max(1, min(PAGE_SIZE_MAX, int(limit)))
    report = await db.scalar(select(FinancialReportModel).where(
        FinancialReportModel.id == report_id, FinancialReportModel.user_id == user_id,
    ))
    if report is None or report.status != "ready":
        return {"status": "unavailable", "report_id": str(report_id), "items": [], "next_cursor": None}
    decoded = _cursor_decode(cursor)
    query = select(FinancialChangeEventModel).where(
        FinancialChangeEventModel.report_id == report_id,
        FinancialChangeEventModel.user_id == user_id,
    )
    if decoded:
        cursor_time, cursor_id = decoded
        query = query.where(
            (FinancialChangeEventModel.observed_at > cursor_time)
            | ((FinancialChangeEventModel.observed_at == cursor_time) & (FinancialChangeEventModel.id > cursor_id))
        )
    rows = list((await db.scalars(query.order_by(
        FinancialChangeEventModel.observed_at, FinancialChangeEventModel.id
    ).limit(limit + 1))).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "status": "ready", "report_id": str(report_id),
        "items": [_event_data(row) for row in rows],
        "next_cursor": _cursor_encode(rows[-1].observed_at, rows[-1].id) if has_more and rows else None,
    }

