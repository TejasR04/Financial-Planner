from datetime import datetime, timezone
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
    assert "transactions.posted_at >" in sql
    assert "accounts.archived_at IS NULL" in sql


def test_loan_transfer_rule_keeps_destination():
    from app.domain.merchant_rules import merchant_matches_rule
    rule = LoanBalanceRuleCreate(mode="merchant", merchant_pattern="Online transfer to Auto Loan transaction# 12345678")
    assert rule.merchant_pattern == "online transfer to auto loan"
    assert not merchant_matches_rule("Online transfer to Savings", rule.merchant_pattern, collapse_transfers=False)
