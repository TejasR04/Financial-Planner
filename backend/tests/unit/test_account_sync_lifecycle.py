"""Lifecycle contracts for the Accounts/Plaid boundary without a live bank."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ProviderError
from app.domain.entities import Account, Institution
from app.domain.enums import AccountStatus, AccountType, InstitutionStatus, ProviderType
from app.providers.plaid_client import RawPlaidAccount
from app.providers.plaid_provider import PlaidProvider
from app.persistence.repositories.account_repository import AccountRepository
from app.schemas.account import AccountCreateRequest
from app.schemas.user import UserUpdateRequest


def _account(*, type_: AccountType = AccountType.DEPOSITORY, balance: str = "100") -> Account:
    return Account(
        id=uuid4(),
        user_id=uuid4(),
        name="Test account",
        type=type_,
        balance=Decimal(balance),
    )


def test_usd_is_the_only_accepted_user_and_manual_account_currency():
    assert UserUpdateRequest(base_currency="USD").base_currency == "USD"
    assert AccountCreateRequest(name="Cash", type=AccountType.DEPOSITORY, balance="10").currency == "USD"

    with pytest.raises(PydanticValidationError):
        UserUpdateRequest(base_currency="EUR")
    with pytest.raises(PydanticValidationError):
        AccountCreateRequest(name="Cash", type=AccountType.DEPOSITORY, balance="10", currency="CAD")


def test_liability_grouping_is_type_based_not_balance_sign_based():
    assert _account(type_=AccountType.DEPOSITORY, balance="-25").is_liability is False
    assert _account(type_=AccountType.CREDIT, balance="25").is_liability is True


@pytest.mark.asyncio
async def test_manual_credit_balance_is_normalized_to_the_liability_sign_convention():
    row = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        name="Card",
        type=AccountType.CREDIT.value,
        balance=Decimal("0"),
        currency="USD",
        institution_id=None,
        mask=None,
        apy=None,
        status=AccountStatus.MANUAL.value,
        updated_at=None,
        external_account_id=None,
        archived_at=None,
    )
    repository = AccountRepository(SimpleNamespace(flush=AsyncMock()))
    repository._row_for_user = AsyncMock(return_value=row)

    updated = await repository.update_manual_for_user(row.user_id, row.id, balance=Decimal("2500"))

    assert updated.balance == Decimal("-2500")


@pytest.mark.asyncio
async def test_refresh_archives_removed_accounts_and_tolerates_missing_holdings():
    user_id = uuid4()
    institution_id = uuid4()
    institution = Institution(
        id=institution_id,
        user_id=user_id,
        name="Test bank",
        provider=ProviderType.PLAID,
        status=InstitutionStatus.HEALTHY,
    )
    raw_account = RawPlaidAccount(
        external_account_id="plaid-account-1",
        name="Checking",
        official_name=None,
        plaid_type="depository",
        plaid_subtype="checking",
        mask="1234",
        currency="USD",
        current_balance=Decimal("125"),
        available_balance=Decimal("100"),
    )
    provider = object.__new__(PlaidProvider)
    provider._institutions = SimpleNamespace(
        lock_for_sync=AsyncMock(return_value=institution),
        get_decrypted_access_token=AsyncMock(return_value="access-token"),
        get_sync_cursor=AsyncMock(return_value=None),
        mark_sync_success=AsyncMock(return_value=institution),
    )
    provider._accounts = SimpleNamespace(
        upsert_from_plaid=AsyncMock(),
        archive_missing_from_plaid=AsyncMock(),
    )
    provider._transactions = SimpleNamespace(apply_plaid_updates=AsyncMock(return_value=(0, 0, 0)))
    provider._holdings = SimpleNamespace(replace_for_accounts=AsyncMock())
    provider._client = SimpleNamespace(
        get_accounts=AsyncMock(return_value=[raw_account]),
        sync_transactions=AsyncMock(
            return_value=SimpleNamespace(added_or_modified=[], removed_external_transaction_ids=[], next_cursor="cursor-1")
        ),
        get_holdings=AsyncMock(side_effect=ProviderError("Investments is unavailable")),
    )
    provider._account_id_map = AsyncMock(return_value={"plaid-account-1": uuid4()})

    result = await provider._refresh_institution(user_id, institution)

    assert result.status == "healthy"
    assert result.holdings_synced == 0
    provider._accounts.archive_missing_from_plaid.assert_awaited_once_with(
        user_id, institution_id, ["plaid-account-1"]
    )
    provider._institutions.mark_sync_success.assert_awaited_once_with(institution_id, "cursor-1")


@pytest.mark.asyncio
async def test_holdings_access_is_scoped_to_the_authenticated_user_before_refreshing():
    user_id = uuid4()
    account_id = uuid4()
    provider = object.__new__(PlaidProvider)
    provider._accounts = SimpleNamespace(get_for_user=AsyncMock())
    provider._holdings = SimpleNamespace(list_for_account=AsyncMock(return_value=[]))
    provider.refresh = AsyncMock()

    assert await provider.get_holdings(user_id, account_id) == []
    provider._accounts.get_for_user.assert_awaited_once_with(user_id, account_id)
    provider.refresh.assert_awaited_once_with(user_id)
