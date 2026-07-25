"""PlaidProvider — implements FinancialDataProvider using Plaid as the
upstream source, plus the extra link-flow methods (`create_link_token`,
`link_new_institution`) that don't fit that interface since they're
onboarding operations, not periodic data reads.

The refresh path synchronizes accounts, cursor-based Transactions patches,
and current investment holdings for every linked Item.

This is the only place (besides `plaid_client.py`) that ever sees a
decrypted Plaid access token, and it never returns one — every public
method here returns domain entities or Phase-A-specific dataclasses with
no token field.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProviderError
from app.domain.entities import Account, Holding, Institution, Transaction
from app.domain.enums import AccountStatus, AccountType, AssetClass, TransactionStatus, TransactionType
from app.persistence.repositories.account_repository import AccountRepository
from app.persistence.repositories.holding_repository import HoldingRepository
from app.persistence.repositories.institution_repository import InstitutionRepository
from app.persistence.repositories.transaction_repository import TransactionRepository
from app.providers.base import FinancialDataProvider
from app.providers.plaid_client import PlaidClient, RawPlaidAccount, RawPlaidHolding, RawPlaidTransaction

# Plaid (type, subtype) -> our AccountType. Falls back by `type` alone if
# the subtype isn't one we've special-cased.
_SUBTYPE_MAP: dict[str, AccountType] = {
    "401k": AccountType.RETIREMENT,
    "403b": AccountType.RETIREMENT,
    "457b": AccountType.RETIREMENT,
    "ira": AccountType.RETIREMENT,
    "roth": AccountType.RETIREMENT,
    "roth 401k": AccountType.RETIREMENT,
    "pension": AccountType.RETIREMENT,
    "hsa": AccountType.RETIREMENT,
    "mortgage": AccountType.LOAN,
    "student": AccountType.LOAN,
    "auto": AccountType.LOAN,
}
_TYPE_MAP: dict[str, AccountType] = {
    "depository": AccountType.DEPOSITORY,
    "investment": AccountType.INVESTMENT,
    "credit": AccountType.CREDIT,
    "loan": AccountType.LOAN,
}
_LIABILITY_TYPES = {AccountType.CREDIT, AccountType.LOAN}


@dataclass(slots=True)
class LinkTokenResult:
    link_token: str
    expiration: datetime


@dataclass(slots=True)
class LinkedInstitutionResult:
    institution: Institution
    accounts: list[Account]


@dataclass(slots=True)
class PlaidRefreshResult:
    institution_id: UUID
    institution_name: str
    status: str
    accounts_synced: int = 0
    transactions_created: int = 0
    transactions_updated: int = 0
    transactions_removed: int = 0
    holdings_synced: int = 0
    error: str | None = None


def _map_account_type(raw: RawPlaidAccount) -> AccountType:
    if raw.plaid_subtype and raw.plaid_subtype in _SUBTYPE_MAP:
        return _SUBTYPE_MAP[raw.plaid_subtype]
    return _TYPE_MAP.get(raw.plaid_type, AccountType.DEPOSITORY)


def _map_balance(raw: RawPlaidAccount, account_type: AccountType) -> Decimal:
    balance = raw.current_balance if raw.current_balance is not None else Decimal("0")
    # Plaid reports credit/loan balances as a positive amount owed; this
    # app represents liabilities as negative balances (see AccountsPage
    # net-worth math), so flip the sign for those types.
    if account_type in _LIABILITY_TYPES and balance > 0:
        return -balance
    return balance


class PlaidProvider(FinancialDataProvider):
    def __init__(self, session: AsyncSession, client_id: str | None, secret: str | None, environment: str = "sandbox"):
        self.session = session
        self._client = PlaidClient(client_id, secret, environment)
        self._institutions = InstitutionRepository(session)
        self._accounts = AccountRepository(session)
        self._transactions = TransactionRepository(session)
        self._holdings = HoldingRepository(session)

    # -- Link flow (Phase A) --------------------------------------------

    async def create_link_token(
        self,
        user_id: UUID,
        institution_id: UUID | None = None,
    ) -> LinkTokenResult:
        access_token = None
        if institution_id is not None:
            access_token = await self._institutions.get_decrypted_access_token_for_user(
                institution_id,
                user_id,
            )
        result = await self._client.create_link_token(user_id, update_access_token=access_token)
        return LinkTokenResult(link_token=result.link_token, expiration=result.expiration)

    async def link_new_institution(self, user_id: UUID, public_token: str) -> LinkedInstitutionResult:
        """Exchange a Link `public_token` for an access token, persist the
        new Institution (token encrypted at rest), fetch its accounts from
        Plaid, and persist those too. Returns domain entities only.
        """
        exchange = await self._client.exchange_public_token(public_token)

        existing = await self._institutions.get_by_external_item_id(exchange.item_id)
        if existing is not None:
            raise ProviderError("This institution is already linked")

        institution_name = await self._client.get_institution_name(exchange.access_token)
        institution = await self._institutions.create_from_plaid(
            user_id=user_id,
            name=institution_name,
            external_item_id=exchange.item_id,
            access_token=exchange.access_token,
        )

        raw_accounts = await self._client.get_accounts(exchange.access_token)
        accounts = [_to_account_entity(user_id, institution.id, raw) for raw in raw_accounts]
        return LinkedInstitutionResult(institution=institution, accounts=accounts)

    # -- Refresh and FinancialDataProvider interface ----------------------

    async def refresh(self, user_id: UUID) -> list[PlaidRefreshResult]:
        """Refresh each linked Item independently so one failed bank does
        not prevent the rest of the user's portfolio from updating.
        """
        institutions = await self._institutions.list_plaid_for_user(user_id)
        results: list[PlaidRefreshResult] = []
        for institution in institutions:
            try:
                # Keep an Item atomic: a failed holdings call must not move
                # its transaction cursor forward or leave a half-refreshed
                # account snapshot behind.
                async with self.session.begin_nested():
                    result = await self._refresh_institution(user_id, institution)
                results.append(result)
            except ProviderError as exc:
                await self._institutions.mark_sync_error(institution.id)
                results.append(
                    PlaidRefreshResult(
                        institution_id=institution.id,
                        institution_name=institution.name,
                        status="error",
                        error=str(exc),
                    )
                )
        return results

    async def refresh_institution(self, user_id: UUID, institution_id: UUID) -> PlaidRefreshResult:
        """Refresh one linked Item after verifying ownership and serializing
        cursor updates for that Item."""
        institution = await self._institutions.get_for_user(user_id, institution_id)
        if institution.provider.value != "plaid":
            raise ProviderError("Only Plaid institutions can be synced")
        try:
            async with self.session.begin_nested():
                return await self._refresh_institution(user_id, institution)
        except ProviderError:
            await self._institutions.mark_sync_error(institution_id)
            raise

    async def _refresh_institution(self, user_id: UUID, institution: Institution) -> PlaidRefreshResult:
        # Lock the Item row before reading or advancing its transaction
        # cursor. This prevents concurrent browser sessions from applying
        # overlapping patches out of order.
        institution = await self._institutions.lock_for_sync(user_id, institution.id)
        access_token = await self._institutions.get_decrypted_access_token(institution.id)
        raw_accounts = await self._client.get_accounts(access_token)
        for raw_account in raw_accounts:
            await self._accounts.upsert_from_plaid(
                user_id, _to_account_entity(user_id, institution.id, raw_account)
            )
        await self._accounts.archive_missing_from_plaid(
            user_id,
            institution.id,
            [account.external_account_id for account in raw_accounts],
        )

        cursor = await self._institutions.get_sync_cursor(institution.id)
        transaction_patch = await self._client.sync_transactions(access_token, cursor)
        account_map = await self._account_id_map(user_id, institution.id)
        transactions = [
            _to_transaction_entity(raw, account_map[raw.external_account_id])
            for raw in transaction_patch.added_or_modified
            if raw.external_account_id in account_map
        ]
        created, updated, removed = await self._transactions.apply_plaid_updates(
            transactions, transaction_patch.removed_external_transaction_ids
        )

        # Investment holdings are optional for a Transactions-linked Item.
        # A bank without Investments support must still sync balances and
        # transactions successfully.
        try:
            holding_account_external_ids, raw_holdings = await self._client.get_holdings(access_token)
            holding_account_ids = [
                account_map[external_id]
                for external_id in holding_account_external_ids
                if external_id in account_map
            ]
            holdings = [
                _to_holding_entity(raw, account_map[raw.external_account_id])
                for raw in raw_holdings
                if raw.external_account_id in account_map
            ]
            saved_holdings = await self._holdings.replace_for_accounts(holding_account_ids, holdings)
        except ProviderError:
            saved_holdings = []
        await self._institutions.mark_sync_success(institution.id, transaction_patch.next_cursor)
        return PlaidRefreshResult(
            institution_id=institution.id,
            institution_name=institution.name,
            status="healthy",
            accounts_synced=len(raw_accounts),
            transactions_created=created,
            transactions_updated=updated,
            transactions_removed=removed,
            holdings_synced=len(saved_holdings),
        )

    async def get_accounts(self, user_id: UUID) -> list[Account]:
        await self.refresh(user_id)
        return await self._accounts.list_for_user(user_id)

    async def get_transactions(self, user_id: UUID, since: date) -> list[Transaction]:
        await self.refresh(user_id)
        return await self._transactions.list_since_for_income_expense(user_id, since)

    async def get_holdings(self, user_id: UUID, account_id: UUID) -> list[Holding]:
        await self._accounts.get_for_user(user_id, account_id)
        await self.refresh(user_id)
        return await self._holdings.list_for_account(account_id)

    async def _account_id_map(self, user_id: UUID, institution_id: UUID) -> dict[str, UUID]:
        accounts = await self._accounts.list_for_user(user_id)
        return {
            account.external_account_id: account.id
            for account in accounts
            if account.institution_id == institution_id and account.external_account_id is not None
        }


def _to_account_entity(user_id: UUID, institution_id: UUID, raw: RawPlaidAccount) -> Account:
    if raw.currency != "USD":
        raise ProviderError("Meridian currently supports U.S. dollar accounts only")
    account_type = _map_account_type(raw)
    return Account(
        id=uuid4(),
        user_id=user_id,
        name=raw.official_name or raw.name,
        type=account_type,
        balance=_map_balance(raw, account_type),
        currency=raw.currency,
        institution_id=institution_id,
        mask=raw.mask,
        status=AccountStatus.CONNECTED,
        external_account_id=raw.external_account_id,
    )


def _to_transaction_entity(raw: RawPlaidTransaction, account_id: UUID) -> Transaction:
    if raw.category.startswith("TRANSFER"):
        transaction_type = TransactionType.TRANSFER
    elif raw.amount > 0:
        transaction_type = TransactionType.INCOME
    else:
        transaction_type = TransactionType.EXPENSE
    return Transaction(
        id=uuid4(),
        account_id=account_id,
        posted_at=raw.posted_at,
        merchant=raw.merchant,
        category=raw.category,
        amount=raw.amount,
        type=transaction_type,
        status=TransactionStatus.PENDING if raw.pending else TransactionStatus.CLEARED,
        external_transaction_id=raw.external_transaction_id,
    )


def _to_holding_entity(raw: RawPlaidHolding, account_id: UUID) -> Holding:
    return Holding(
        id=uuid4(),
        account_id=account_id,
        symbol=raw.symbol,
        quantity=raw.quantity,
        cost_basis=raw.cost_basis,
        market_value=raw.market_value,
        asset_class=_map_asset_class(raw),
        as_of=raw.as_of,
    )


def _map_asset_class(raw: RawPlaidHolding) -> AssetClass:
    security_type = (raw.security_type or "").lower()
    if raw.is_cash_equivalent or security_type in {"cash", "cash equivalent"}:
        return AssetClass.CASH
    if security_type in {"fixed income", "loan"}:
        return AssetClass.FIXED_INCOME
    if security_type in {"real estate", "reit"}:
        return AssetClass.REAL_ESTATE
    if security_type in {"equity", "etf", "mutual fund"}:
        return AssetClass.EQUITY
    return AssetClass.ALTERNATIVES
