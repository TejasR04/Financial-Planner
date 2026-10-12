from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.financial_date import financial_today
from app.persistence.models import (
    AccountModel,
    BudgetCategoryModel,
    HoldingModel,
    LoanBalanceRuleModel,
    TransactionModel,
    UserModel,
)
from app.persistence.reporting_models import FinancialChangeEventModel, FinancialReportModel
from app.services import daily_reports
from app.services.daily_reports import capture_daily_report, enable_reporting, get_report_changes


@pytest.mark.asyncio
async def test_enrollment_baseline_keeps_a_consistent_view_of_concurrent_writes(test_engine, client, monkeypatch):
    user_id, account_id = uuid4(), uuid4()
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as setup:
        setup.add(UserModel(id=user_id, email=f"{user_id}@example.com", hashed_password="test", full_name="Baseline"))
        await setup.flush()
        setup.add(AccountModel(id=account_id, user_id=user_id, name="Cash", type="depository",
                               currency="USD", status="manual", balance=Decimal("100.00")))
        await setup.commit()

    original_snapshot = daily_reports._load_snapshot
    async def snapshot_with_concurrent_write(reader, owner, captured_at, **kwargs):
        # Enrollment has already selected its eligible events in the reader's
        # snapshot. This commit must be absent from both the baseline values
        # and its event membership, and appear in the next report instead.
        async with factory() as writer:
            await writer.execute(update(AccountModel).where(AccountModel.id == account_id)
                                 .values(balance=Decimal("200.00")))
            await writer.commit()
        return await original_snapshot(reader, owner, captured_at, **kwargs)

    monkeypatch.setattr(daily_reports, "_load_snapshot", snapshot_with_concurrent_write)
    async with factory() as enrollment:
        await daily_reports.enable_reporting(enrollment, user_id)
        await enrollment.commit()
        baseline = await enrollment.scalar(select(FinancialReportModel).where(
            FinancialReportModel.user_id == user_id, FinancialReportModel.is_baseline.is_(True)
        ))
        assert baseline.snapshot["summary"]["assets"] == "100.00"
        assert await enrollment.scalar(select(func.count()).select_from(FinancialChangeEventModel).where(
            FinancialChangeEventModel.user_id == user_id, FinancialChangeEventModel.report_id.is_(None)
        )) == 1


@pytest.mark.asyncio
async def test_reports_are_immutable_and_late_commits_appear_in_next_capture(
    test_engine, client, monkeypatch,
) -> None:
    """Audit events roll back with source writes; captures remain immutable and event-complete."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr(daily_reports, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(daily_reports, "engine", test_engine)

    user_id = uuid4()
    account_id = uuid4()
    investment_account_id = uuid4()
    holding_id = uuid4()
    category_id = uuid4()
    today = financial_today()
    async with session_factory() as setup:
        user = UserModel(
            id=user_id, email=f"{user_id}@example.com", hashed_password="test-hash", full_name="Report Test",
        )
        checking = AccountModel(
            id=account_id, user_id=user_id, name="Checking", type="depository", balance=Decimal("1000.00"),
            currency="USD", status="manual",
        )
        investment = AccountModel(
            id=investment_account_id, user_id=user_id, name="Brokerage", type="investment",
            balance=Decimal("2500.00"), currency="USD", status="manual",
        )
        holding = HoldingModel(
            id=holding_id, account_id=investment_account_id, symbol="ABC", quantity=Decimal("10"),
            cost_basis=Decimal("900.00"), market_value=Decimal("1000.00"), asset_class="equity",
            as_of=today,
        )
        category = BudgetCategoryModel(
            id=category_id, user_id=user_id, name="Groceries", group_name="Needs",
            monthly_limit=Decimal("500.00"), sort_order=0, active=True,
        )
        transaction = TransactionModel(
            id=uuid4(), account_id=account_id, posted_at=today.replace(day=1), merchant="Market",
            category="food_and_drink_groceries", amount=Decimal("-87.50"), type="expense", status="cleared",
            budget_category_id=category_id, ignored_from_budget=False,
        )
        setup.add_all([user, checking, investment, holding, category, transaction])
        await setup.commit()

        initial_count = await setup.scalar(
            select(func.count()).select_from(FinancialChangeEventModel).where(FinancialChangeEventModel.user_id == user_id)
        )
        assert initial_count >= 5
        entities = set((await setup.scalars(
            select(FinancialChangeEventModel.entity_type).where(FinancialChangeEventModel.user_id == user_id)
        )).all())
        assert {"accounts", "holdings", "transactions", "budget_categories"}.issubset(entities)
        inserted_account = await setup.scalar(select(FinancialChangeEventModel).where(
            FinancialChangeEventModel.user_id == user_id,
            FinancialChangeEventModel.entity_type == "accounts",
            FinancialChangeEventModel.entity_id == str(account_id),
            FinancialChangeEventModel.operation == "insert",
        ))
        assert inserted_account is not None
        assert inserted_account.after_values["balance"] == "1000.00"

        # Bulk SQL is audited. Rolling back the source update also rolls back its audit row.
        await setup.execute(update(AccountModel).where(AccountModel.id == account_id).values(balance=Decimal("777.00")))
        await setup.rollback()
        rolled_back_count = await setup.scalar(
            select(func.count()).select_from(FinancialChangeEventModel).where(FinancialChangeEventModel.user_id == user_id)
        )
        assert rolled_back_count == initial_count

        await enable_reporting(setup, user_id)
        await setup.commit()
        baseline = await setup.scalar(select(FinancialReportModel).where(
            FinancialReportModel.user_id == user_id, FinancialReportModel.is_baseline.is_(True),
        ))
        assert baseline is not None and baseline.status == "ready"
        assert baseline.snapshot["budgets"]["categories"][0]["monthly_limit"] == "500.00"
        assert baseline.snapshot["budgets"]["categories"][0]["spent"] == "87.50"
        assigned_events = await setup.scalar(
            select(func.count()).select_from(FinancialChangeEventModel).where(
                FinancialChangeEventModel.user_id == user_id,
                FinancialChangeEventModel.report_id == baseline.id,
            )
        )
        assert assigned_events == initial_count

    first_date = today
    first = await capture_daily_report(user_id, first_date)
    assert first["status"] == "ready"
    assert first["summary"]["assets"] == "3500.00"
    first_id = first["report_id"]

    # Re-running a completed date returns the original report even if source rows change later.
    async with session_factory() as edit:
        await edit.execute(update(AccountModel).where(AccountModel.id == account_id).values(balance=Decimal("1200.00")))
        await edit.commit()
    repeated = await capture_daily_report(user_id, first_date)
    assert repeated["report_id"] == first_id
    assert repeated["summary"]["assets"] == "3500.00"

    # A transaction open at the capture boundary is absent from both the consistent snapshot
    # and event set. Its late commit is assigned to the next daily report.
    late_session = session_factory()
    await late_session.begin()
    await late_session.execute(update(AccountModel).where(AccountModel.id == account_id).values(balance=Decimal("1300.00")))
    second = await capture_daily_report(user_id, today + timedelta(days=1))
    assert second["summary"]["assets"] == "3700.00"
    assert second["changes"]["audited_event_count"] == 1
    await late_session.commit()
    await late_session.close()

    third = await capture_daily_report(user_id, today + timedelta(days=2))
    assert third["summary"]["assets"] == "3800.00"
    assert third["changes"]["audited_event_count"] == 1
    assert third["changes"]["accounts"][0]["fields"]["balance"]["change"] == "100.00"
    async with session_factory() as reader:
        page = await get_report_changes(reader, user_id, UUID(third["report_id"]), limit=10)
        assert page["status"] == "ready"
        assert len(page["items"]) == 1
        assert page["items"][0]["entity_type"] == "accounts"

    async with session_factory() as cleanup:
        await cleanup.execute(delete(TransactionModel).where(TransactionModel.account_id.in_([account_id, investment_account_id])))
        await cleanup.execute(delete(HoldingModel).where(HoldingModel.account_id == investment_account_id))
        await cleanup.execute(delete(AccountModel).where(AccountModel.user_id == user_id))
        await cleanup.execute(delete(BudgetCategoryModel).where(BudgetCategoryModel.user_id == user_id))
        await cleanup.execute(delete(UserModel).where(UserModel.id == user_id))
        await cleanup.commit()


@pytest.mark.asyncio
async def test_bulk_account_delete_preserves_cascade_audit_ownership(test_engine, client) -> None:
    """Audit triggers retain the right owner when several accounts cascade together."""
    user_id = uuid4()
    account_ids = [uuid4(), uuid4()]
    async with AsyncSession(test_engine, expire_on_commit=False) as db:
        db.add(UserModel(
            id=user_id, email=f"{user_id}@example.com", hashed_password="test-hash", full_name="Cascade Test",
        ))
        accounts = [
            AccountModel(
                id=account_id, user_id=user_id, name=f"Loan {index}", type="loan",
                balance=Decimal("-100.00"), currency="USD", status="manual",
            )
            for index, account_id in enumerate(account_ids)
        ]
        rules = [
            LoanBalanceRuleModel(
                account_id=account_id, mode="fixed", amount=Decimal("25.00"), active=True,
            )
            for account_id in account_ids
        ]
        db.add_all([*accounts, *rules])
        await db.commit()

        await db.execute(delete(AccountModel).where(AccountModel.id.in_(account_ids)))
        await db.commit()
        cascade_events = list((await db.scalars(select(FinancialChangeEventModel).where(
            FinancialChangeEventModel.user_id == user_id,
            FinancialChangeEventModel.entity_type == "loan_balance_rules",
            FinancialChangeEventModel.operation == "delete",
        ))).all())
        assert len(cascade_events) == 2
        assert all(event.user_id == user_id for event in cascade_events)
        assert {event.entity_id for event in cascade_events} == {str(rule.id) for rule in rules}

        await db.execute(delete(UserModel).where(UserModel.id == user_id))
        await db.commit()

