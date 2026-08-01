from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.domain.entities import Account, Transaction
from app.domain.enums import AccountType, TransactionStatus, TransactionType
from app.persistence.repositories.account_repository import AccountRepository
from app.persistence.repositories.holding_repository import HoldingRepository
from app.persistence.repositories.investment_value_snapshot_repository import (
    InvestmentValueSnapshotRepository,
)
from app.persistence.repositories.liability_repository import LiabilityRepository
from app.persistence.repositories.transaction_repository import TransactionRepository


def _sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def _empty_result():
    return SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: []),
        all=lambda: [],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("repository_type", [HoldingRepository, LiabilityRepository])
async def test_active_child_queries_exclude_archived_accounts(repository_type):
    session = SimpleNamespace(execute=AsyncMock(return_value=_empty_result()))

    assert await repository_type(session).list_for_user(uuid4()) == []

    statement = session.execute.await_args.args[0]
    assert "accounts.archived_at IS NULL" in _sql(statement)


@pytest.mark.asyncio
async def test_unlink_detaches_already_archived_accounts_too():
    session = SimpleNamespace(execute=AsyncMock(), flush=AsyncMock())

    await AccountRepository(session).archive_and_detach_institution(uuid4(), uuid4())

    statement = session.execute.await_args.args[0]
    sql = _sql(statement)
    assert "accounts.archived_at IS NULL" not in sql.split("WHERE", 1)[1]
    assert {column.key for column in statement._values} == {"archived_at", "institution_id"}


@pytest.mark.asyncio
async def test_complete_history_query_has_no_hidden_limit():
    session = SimpleNamespace(execute=AsyncMock(return_value=_empty_result()))

    assert await TransactionRepository(session).list_since_for_income_expense(
        uuid4(), date(2025, 1, 1)
    ) == []

    statement = session.execute.await_args.args[0]
    assert "LIMIT" not in _sql(statement).upper()


@pytest.mark.asyncio
async def test_paginated_transaction_order_has_stable_id_tiebreaker():
    count_result = SimpleNamespace(scalar_one=lambda: 0)
    rows_result = _empty_result()
    session = SimpleNamespace(
        execute=AsyncMock(side_effect=[count_result, rows_result])
    )

    rows, total = await TransactionRepository(session).list_for_user(uuid4())

    assert rows == []
    assert total == 0
    sql = _sql(session.execute.await_args_list[1].args[0])
    assert "transactions.posted_at DESC, transactions.id DESC" in sql


@pytest.mark.asyncio
async def test_transaction_totals_are_aggregated_in_sql():
    result = SimpleNamespace(all=lambda: [("income", Decimal("25.00"))])
    session = SimpleNamespace(execute=AsyncMock(return_value=result))

    totals = await TransactionRepository(session).totals_by_type_since(
        uuid4(), date(2025, 1, 1), absolute=True
    )

    assert totals == {TransactionType.INCOME: Decimal("25.00")}
    assert "sum(abs(transactions.amount))" in _sql(session.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_plaid_update_prefetches_all_existing_transactions_once():
    existing = SimpleNamespace(
        external_transaction_id="existing",
        account_id=uuid4(),
        posted_at=date(2025, 1, 1),
        merchant="Old",
        category="Old",
        amount=Decimal("1"),
        type=TransactionType.EXPENSE.value,
        status=TransactionStatus.CLEARED.value,
    )
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [existing]))
    session = SimpleNamespace(execute=AsyncMock(return_value=result), add=Mock(), flush=AsyncMock())
    account_id = uuid4()
    transactions = [
        Transaction(
            id=uuid4(),
            account_id=account_id,
            posted_at=date(2025, 2, index),
            merchant=f"Merchant {index}",
            category="Category",
            amount=Decimal("-1"),
            type=TransactionType.EXPENSE,
            status=TransactionStatus.CLEARED,
            external_transaction_id=external_id,
        )
        for index, external_id in [(1, "existing"), (2, "new")]
    ]

    counts = await TransactionRepository(session).apply_plaid_updates(transactions, [])

    assert counts == (1, 1, 0)
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_daily_snapshots_prefetch_existing_rows_once():
    session = SimpleNamespace(execute=AsyncMock(return_value=_empty_result()), add=Mock(), flush=AsyncMock())
    accounts = [
        Account(
            id=uuid4(),
            user_id=uuid4(),
            name=f"Investment {index}",
            type=AccountType.INVESTMENT,
            balance=Decimal("100"),
        )
        for index in range(3)
    ]

    await InvestmentValueSnapshotRepository(session).record_for_accounts(accounts)

    assert session.execute.await_count == 1
    assert session.add.call_count == 3
