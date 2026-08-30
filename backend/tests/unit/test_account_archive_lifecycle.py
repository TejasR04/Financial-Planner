from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.core.exceptions import ValidationError
from app.domain.entities import Account
from app.domain.enums import AccountStatus, AccountType
from app.persistence.repositories.account_repository import AccountRepository
from app.providers.plaid_provider import PlaidProvider


def _row(*, institution_id=None, external_account_id=None, archived_at=None, user_archived_at=None):
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        institution_id=institution_id,
        name="Checking",
        custom_name=None,
        type=AccountType.DEPOSITORY.value,
        balance=Decimal("100"),
        currency="USD",
        mask="1234",
        apy=None,
        status=AccountStatus.CONNECTED.value,
        updated_at=None,
        external_account_id=external_account_id,
        archived_at=archived_at,
        user_archived_at=user_archived_at,
        provider_archived_at=None,
    )


@pytest.mark.asyncio
async def test_archiving_linked_account_retains_institution_relationship():
    institution_id = uuid4()
    row = _row(institution_id=institution_id, external_account_id="plaid-1")
    repository = AccountRepository(SimpleNamespace(flush=AsyncMock()))
    repository._row_for_user = AsyncMock(return_value=row)

    await repository.archive_linked_account(row.user_id, row.id)

    assert row.institution_id == institution_id
    assert row.archived_at is not None
    assert row.user_archived_at == row.archived_at


@pytest.mark.asyncio
async def test_plaid_upsert_does_not_reactivate_user_archived_account():
    archived_at = datetime.now(timezone.utc)
    row = _row(
        institution_id=uuid4(),
        external_account_id="plaid-1",
        archived_at=archived_at,
        user_archived_at=archived_at,
    )
    result = SimpleNamespace(scalar_one_or_none=lambda: row)
    session = SimpleNamespace(execute=AsyncMock(return_value=result), flush=AsyncMock())
    account = Account(
        id=uuid4(),
        user_id=row.user_id,
        name="Checking",
        type=AccountType.DEPOSITORY,
        balance=Decimal("125"),
        institution_id=row.institution_id,
        external_account_id="plaid-1",
        status=AccountStatus.CONNECTED,
    )

    assert await AccountRepository(session).upsert_from_plaid(row.user_id, account) is None
    session.flush.assert_not_awaited()
    assert row.archived_at == archived_at


@pytest.mark.asyncio
async def test_relinking_same_plaid_account_reattaches_retained_history():
    archived_at = datetime.now(timezone.utc)
    new_institution_id = uuid4()
    row = _row(
        external_account_id="plaid-1",
        archived_at=archived_at,
        user_archived_at=archived_at,
    )
    # A full institution unlink leaves the historical row detached.
    assert row.institution_id is None
    result = SimpleNamespace(scalar_one_or_none=lambda: row)
    session = SimpleNamespace(execute=AsyncMock(return_value=result), flush=AsyncMock())
    account = Account(
        id=uuid4(),
        user_id=row.user_id,
        name="Checking",
        type=AccountType.DEPOSITORY,
        balance=Decimal("125"),
        institution_id=new_institution_id,
        external_account_id="plaid-1",
        status=AccountStatus.CONNECTED,
    )

    restored = await AccountRepository(session).upsert_from_plaid(row.user_id, account)

    assert restored is not None
    assert row.institution_id == new_institution_id
    assert row.archived_at is None
    assert row.user_archived_at is None
    assert restored.id == row.id


@pytest.mark.asyncio
async def test_restore_rejects_disconnected_plaid_account():
    row = _row(external_account_id="plaid-1", archived_at=datetime.now(timezone.utc))
    result = SimpleNamespace(scalar_one_or_none=lambda: row)
    session = SimpleNamespace(execute=AsyncMock(return_value=result), flush=AsyncMock())

    with pytest.raises(ValidationError, match="Reconnect the institution"):
        await AccountRepository(session).restore_for_user(row.user_id, row.id)


@pytest.mark.asyncio
async def test_sync_account_map_includes_hidden_accounts_still_linked_to_item():
    institution_id = uuid4()
    hidden = Account(
        id=uuid4(),
        user_id=uuid4(),
        name="Hidden",
        type=AccountType.DEPOSITORY,
        balance=Decimal("10"),
        institution_id=institution_id,
        external_account_id="plaid-hidden",
        archived_at=datetime.now(timezone.utc),
    )
    provider = object.__new__(PlaidProvider)
    provider._accounts = SimpleNamespace(
        list_for_institution_for_sync=AsyncMock(return_value=[hidden])
    )

    result = await provider._account_id_map(hidden.user_id, institution_id)

    assert result == {"plaid-hidden": hidden.id}


@pytest.mark.asyncio
async def test_sync_account_query_does_not_filter_archived_rows():
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
        )
    )

    await AccountRepository(session).list_for_institution_for_sync(uuid4(), uuid4())

    sql = str(session.execute.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "accounts.archived_at IS NULL" not in sql


@pytest.mark.asyncio
async def test_disconnected_summary_counts_soft_deleted_transactions_for_purge():
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[1, 4]))

    assert await AccountRepository(session).disconnected_imported_data_summary(uuid4()) == (1, 4)

    transaction_count_query = session.scalar.await_args_list[1].args[0]
    sql = str(transaction_count_query.compile(dialect=postgresql.dialect()))
    assert "transactions.deleted_at IS NULL" not in sql
