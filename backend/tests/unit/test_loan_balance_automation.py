from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.schemas.loan_balance_rule import LoanBalanceRuleCreate
from app.services.loan_balance_automation_service import LoanBalanceAutomationService


def test_rule_removes_changing_payment_references():
    rule = LoanBalanceRuleCreate(mode="merchant", merchant_pattern="Acme Loan Reference 123456789")
    assert rule.merchant_pattern == "acme loan"


@pytest.mark.asyncio
async def test_payment_matching_filters_and_repeated_application():
    payment = SimpleNamespace(id=uuid4(), merchant="ACME LOAN Reference 987654321", amount=Decimal("-75"))
    unrelated = SimpleNamespace(id=uuid4(), merchant="ACMExpress", amount=Decimal("-90"))
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [payment, unrelated]))), add=Mock())
    service = LoanBalanceAutomationService(session)
    service._already_applied = AsyncMock(side_effect=[False, True])
    service._transaction_already_applied = AsyncMock(return_value=False)
    account = SimpleNamespace(id=uuid4(), balance=Decimal("-100"))
    rule = SimpleNamespace(id=uuid4(), merchant_pattern="Acme Loan", created_at=datetime.now(timezone.utc), active=True)
    assert await service._apply_merchant(rule, account, uuid4()) == 1
    assert account.balance == Decimal("-25")
    assert await service._apply_merchant(rule, account, uuid4()) == 0
    assert account.balance == Decimal("-25")
    sql = str(session.execute.call_args.args[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "transactions.amount < 0" in sql
    assert "transactions.status = 'cleared'" in sql
    assert "transactions.deleted_at IS NULL" in sql
    assert "transactions.posted_at >=" in sql
    assert "accounts.archived_at IS NULL" in sql


@pytest.mark.asyncio
async def test_overlapping_rule_skips_transaction_already_applied_to_target_loan():
    payment = SimpleNamespace(id=uuid4(), merchant="Acme Loan", amount=Decimal("-75"))
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [payment]))
    session = SimpleNamespace(execute=AsyncMock(return_value=result), add=Mock())
    service = LoanBalanceAutomationService(session)
    service._already_applied = AsyncMock(return_value=False)
    service._transaction_already_applied = AsyncMock(return_value=True)
    account = SimpleNamespace(id=uuid4(), balance=Decimal("-100"))
    rule = SimpleNamespace(
        id=uuid4(), merchant_pattern="acme", created_at=datetime.now(timezone.utc), active=True,
    )
    assert await service._apply_merchant(rule, account, uuid4()) == 0
    assert account.balance == Decimal("-100")
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_reconcile_does_not_reapply_an_unchanged_capped_payment():
    transaction_id = uuid4()
    account = SimpleNamespace(id=uuid4(), balance=Decimal("0"))
    posted_at = datetime.now(timezone.utc).date()
    transaction = SimpleNamespace(
        id=transaction_id, account_id=uuid4(), posted_at=posted_at, deleted_at=None,
        status="cleared", amount=Decimal("-100"), merchant="Acme Loan"
    )
    rule = SimpleNamespace(id=uuid4(), merchant_pattern="acme loan", active=False,
                           created_at=datetime(2020, 1, 1, tzinfo=timezone.utc), deleted_at=None)
    adjustment = SimpleNamespace(
        id=uuid4(), transaction_id=transaction_id, amount_applied=Decimal("50"),
        source_amount=Decimal("100"), reversed_at=None, reversal_reason=None,
    )
    source = SimpleNamespace(id=transaction.account_id, user_id=uuid4(), archived_at=None)
    user_id = source.user_id
    result = SimpleNamespace(all=lambda: [(adjustment, rule, account, transaction, source)])
    session = SimpleNamespace(execute=AsyncMock(return_value=result), flush=AsyncMock(), add=Mock())

    await LoanBalanceAutomationService(session).reconcile(user_id)

    assert account.balance == Decimal("0")
    assert adjustment.reversed_at is None
    session.add.assert_not_called()


def _reconcile_case(*, current_balance: str, applied: str, source_amount: str, transaction_amount: str,
                    deleted: bool = False, posted_at=None, rule_deleted: bool = False, source_archived: bool = False):
    user_id, target_id, source_id, transaction_id = uuid4(), uuid4(), uuid4(), uuid4()
    account = SimpleNamespace(id=target_id, balance=Decimal(current_balance))
    transaction = SimpleNamespace(
        id=transaction_id, account_id=source_id, posted_at=posted_at or datetime.now(timezone.utc).date(),
        deleted_at=datetime.now(timezone.utc) if deleted else None, status="cleared",
        amount=Decimal(transaction_amount), merchant="Acme Loan",
    )
    rule = SimpleNamespace(
        id=uuid4(), merchant_pattern="acme loan", active=False,
        created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        deleted_at=datetime.now(timezone.utc) if rule_deleted else None,
    )
    adjustment = SimpleNamespace(
        id=uuid4(), transaction_id=transaction_id, amount_applied=Decimal(applied),
        source_amount=Decimal(source_amount), reversed_at=None, reversal_reason=None,
        event_key=f"transaction:{transaction_id}",
    )
    source = SimpleNamespace(
        id=source_id, user_id=user_id,
        archived_at=datetime.now(timezone.utc) if source_archived else None,
    )
    return user_id, account, transaction, rule, adjustment, source


@pytest.mark.asyncio
@pytest.mark.parametrize(("transaction_amount", "deleted", "expected"), [
    ("-10", False, Decimal("-990")), ("-100", True, Decimal("-1000")),
])
async def test_reconcile_corrects_or_removes_a_payment(transaction_amount, deleted, expected):
    values = _reconcile_case(
        current_balance="-900", applied="100", source_amount="100",
        transaction_amount=transaction_amount, deleted=deleted,
    )
    user_id, account, transaction, rule, adjustment, source = values
    result = SimpleNamespace(all=lambda: [(adjustment, rule, account, transaction, source)])
    session = SimpleNamespace(execute=AsyncMock(return_value=result), flush=AsyncMock(), add=Mock())

    await LoanBalanceAutomationService(session).reconcile(user_id)

    assert account.balance == expected
    assert adjustment.reversed_at is not None
    assert session.add.call_count == (0 if deleted else 1)


@pytest.mark.asyncio
async def test_reconcile_recomputes_later_capped_payment_after_earlier_deletion():
    first = _reconcile_case(current_balance="0", applied="80", source_amount="80", transaction_amount="-80", deleted=True)
    user_id, account, tx1, rule1, adj1, source1 = first
    second = _reconcile_case(current_balance="0", applied="20", source_amount="80", transaction_amount="-80")
    _, _, tx2, rule2, adj2, source2 = second
    source2.user_id = user_id
    rule2.created_at = rule1.created_at
    account.id = uuid4()
    rows = [(adj1, rule1, account, tx1, source1), (adj2, rule2, account, tx2, source2)]
    source1.user_id = user_id
    result = SimpleNamespace(all=lambda: rows)
    session = SimpleNamespace(execute=AsyncMock(return_value=result), flush=AsyncMock(), add=Mock())

    await LoanBalanceAutomationService(session).reconcile(user_id)

    assert account.balance == Decimal("-20")
    assert adj1.reversed_at is not None
    assert adj2.reversed_at is not None
    assert session.add.call_args.args[0].amount_applied == Decimal("80")


@pytest.mark.asyncio
async def test_reconcile_keeps_only_one_overlapping_rule_application():
    values = _reconcile_case(current_balance="-800", applied="100", source_amount="100", transaction_amount="-100")
    user_id, account, transaction, rule1, adj1, source = values
    rule2 = SimpleNamespace(**rule1.__dict__)
    rule2.id = uuid4()
    adj2 = SimpleNamespace(**adj1.__dict__)
    adj2.id = uuid4()
    rows = [(adj1, rule1, account, transaction, source), (adj2, rule2, account, transaction, source)]
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)), flush=AsyncMock(), add=Mock())

    await LoanBalanceAutomationService(session).reconcile(user_id)

    assert account.balance == Decimal("-900")
    assert adj1.reversed_at is None
    assert adj2.reversed_at is not None


@pytest.mark.asyncio
async def test_deleted_rule_retains_its_valid_historical_adjustment():
    values = _reconcile_case(
        current_balance="-900", applied="100", source_amount="100",
        transaction_amount="-100", rule_deleted=True,
    )
    user_id, account, transaction, rule, adjustment, source = values
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [(adjustment, rule, account, transaction, source)])),
        flush=AsyncMock(), add=Mock(),
    )
    await LoanBalanceAutomationService(session).reconcile(user_id)
    assert account.balance == Decimal("-900")
    assert adjustment.reversed_at is None
    assert rule.active is False


@pytest.mark.asyncio
async def test_reconcile_preserves_valid_payment_when_source_account_is_archived():
    values = _reconcile_case(
        current_balance="-900", applied="100", source_amount="100",
        transaction_amount="-100", source_archived=True,
    )
    user_id, account, transaction, rule, adjustment, source = values
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [(adjustment, rule, account, transaction, source)])),
        flush=AsyncMock(), add=Mock(),
    )

    await LoanBalanceAutomationService(session).reconcile(user_id)

    assert account.balance == Decimal("-900")
    assert adjustment.reversed_at is None
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_reconcile_reverses_payment_moved_before_rule_start():
    values = _reconcile_case(
        current_balance="-900", applied="100", source_amount="100", transaction_amount="-100",
        posted_at=datetime(2019, 1, 1, tzinfo=timezone.utc).date(),
    )
    user_id, account, transaction, rule, adjustment, source = values
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [(adjustment, rule, account, transaction, source)])),
        flush=AsyncMock(), add=Mock(),
    )
    await LoanBalanceAutomationService(session).reconcile(user_id)
    assert account.balance == Decimal("-1000")
    assert adjustment.reversed_at is not None


def test_manual_loan_interest_uses_elapsed_days_once_and_payment_reduces_future_interest():
    service = LoanBalanceAutomationService(SimpleNamespace())
    account = SimpleNamespace(balance=Decimal("-1000.00"))
    liability = SimpleNamespace(interest_rate=Decimal("0.365"), last_interest_accrual_date=date(2026, 1, 1))

    assert service._accrue_interest(account, liability, date(2026, 1, 2)) == 1
    assert account.balance == Decimal("-1001.00")
    assert service._accrue_interest(account, liability, date(2026, 1, 2)) == 0
    assert account.balance == Decimal("-1001.00")

    account.balance += Decimal("501.00")
    assert service._accrue_interest(account, liability, date(2026, 1, 3)) == 1
    assert account.balance == Decimal("-500.50")


def test_manual_loan_interest_does_not_backfill_without_checkpoint():
    account = SimpleNamespace(balance=Decimal("-1000.00"))
    liability = SimpleNamespace(interest_rate=Decimal("0.12"), last_interest_accrual_date=None)
    assert LoanBalanceAutomationService._accrue_interest(account, liability, date(2026, 1, 2)) == 0
    assert liability.last_interest_accrual_date == date(2026, 1, 2)
    assert account.balance == Decimal("-1000.00")


def test_loan_transfer_rule_keeps_destination():
    from app.domain.merchant_rules import merchant_matches_rule
    rule = LoanBalanceRuleCreate(mode="merchant", merchant_pattern="Online transfer to Auto Loan transaction# 12345678")
    assert rule.merchant_pattern == "online transfer to auto loan"
    assert not merchant_matches_rule("Online transfer to Savings", rule.merchant_pattern, collapse_transfers=False)
