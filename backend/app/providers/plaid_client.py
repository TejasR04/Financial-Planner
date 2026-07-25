"""Thin wrapper around the Plaid SDK. This is the ONLY module allowed to
import `plaid.*` types or touch a Plaid access token in plaintext outside
of `app/core/crypto.py`. Everything it returns is a plain dataclass so
`plaid_provider.py` (and anything above it) never needs to know the SDK
exists.

Security notes:
- `client_id`/`secret` come from Settings (env vars), never hardcoded,
  never logged, never echoed back in any response.
- All Plaid errors are caught and re-raised as `ProviderError` with a
  sanitized message — the raw Plaid exception can include our own
  request payload, so it's never passed through to the API response.
- Every SDK call is a blocking network call; each is run via
  `asyncio.to_thread` so it doesn't block the FastAPI event loop.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import plaid
from plaid.api import plaid_api
from plaid.exceptions import ApiException
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest

from app.core.exceptions import ProviderError

_ENVIRONMENTS = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}


@dataclass(slots=True)
class LinkTokenResult:
    link_token: str
    expiration: datetime


@dataclass(slots=True)
class ExchangeResult:
    access_token: str
    item_id: str


@dataclass(slots=True)
class RawPlaidAccount:
    external_account_id: str
    name: str
    official_name: str | None
    plaid_type: str
    plaid_subtype: str | None
    mask: str | None
    currency: str
    current_balance: Decimal | None
    available_balance: Decimal | None


@dataclass(slots=True)
class RawPlaidTransaction:
    external_transaction_id: str
    external_account_id: str
    posted_at: date
    merchant: str
    category: str
    amount: Decimal
    pending: bool


@dataclass(slots=True)
class RawPlaidHolding:
    external_account_id: str
    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    market_value: Decimal
    security_type: str | None
    is_cash_equivalent: bool
    as_of: date


@dataclass(slots=True)
class TransactionsSyncResult:
    added_or_modified: list[RawPlaidTransaction]
    removed_external_transaction_ids: list[str]
    next_cursor: str


def _sanitize_error(exc: ApiException) -> str:
    """Plaid's ApiException body can include the request we sent (which
    contains our client_id). Surface only the error_code/error_type Plaid
    gives us — never the raw body — to callers and, from there, to the
    frontend.
    """
    try:
        import json

        body = json.loads(exc.body) if exc.body else {}
        error_type = body.get("error_type", "PLAID_ERROR")
        error_code = body.get("error_code", "UNKNOWN")
        return f"Plaid error: {error_type}/{error_code}"
    except Exception:
        return "Plaid error: request failed"


class PlaidClient:
    def __init__(self, client_id: str | None, secret: str | None, environment: str = "sandbox"):
        if not client_id or not secret:
            raise ProviderError("Plaid is not configured: set PLAID_CLIENT_ID and PLAID_SECRET")
        host = _ENVIRONMENTS.get(environment, _ENVIRONMENTS["sandbox"])
        configuration = plaid.Configuration(
            host=host,
            api_key={"clientId": client_id, "secret": secret},
        )
        api_client = plaid.ApiClient(configuration)
        self._client = plaid_api.PlaidApi(api_client)

    async def create_link_token(
        self,
        user_id: UUID,
        update_access_token: str | None = None,
    ) -> LinkTokenResult:
        request_args = {
            "user": LinkTokenCreateRequestUser(client_user_id=str(user_id)),
            "client_name": "Meridian",
            "country_codes": [CountryCode("US")],
            "language": "en",
        }
        if update_access_token is None:
            request_args["products"] = [Products("transactions"), Products("investments")]
        else:
            # Existing Items need update mode to grant a newly requested
            # product under Plaid's Data Transparency Messaging rules.
            request_args["access_token"] = update_access_token
            request_args["additional_consented_products"] = [Products("investments")]
        request = LinkTokenCreateRequest(**request_args)
        try:
            response = await asyncio.to_thread(self._client.link_token_create, request)
        except ApiException as exc:
            raise ProviderError(_sanitize_error(exc)) from exc
        return LinkTokenResult(link_token=response.link_token, expiration=response.expiration)

    async def exchange_public_token(self, public_token: str) -> ExchangeResult:
        request = ItemPublicTokenExchangeRequest(public_token=public_token)
        try:
            response = await asyncio.to_thread(self._client.item_public_token_exchange, request)
        except ApiException as exc:
            raise ProviderError(_sanitize_error(exc)) from exc
        return ExchangeResult(access_token=response.access_token, item_id=response.item_id)

    async def get_institution_name(self, access_token: str) -> str:
        """Best-effort lookup of the human-readable institution name for
        the item behind `access_token`. Falls back to a generic label
        rather than failing the whole link flow if this secondary call
        errors."""
        try:
            item_response = await asyncio.to_thread(
                self._client.item_get, ItemGetRequest(access_token=access_token)
            )
            institution_id = item_response.item.institution_id
            if not institution_id:
                return "Linked institution"
            inst_response = await asyncio.to_thread(
                self._client.institutions_get_by_id,
                InstitutionsGetByIdRequest(institution_id=institution_id, country_codes=[CountryCode("US")]),
            )
            return inst_response.institution.name
        except ApiException:
            return "Linked institution"

    async def get_accounts(self, access_token: str) -> list[RawPlaidAccount]:
        request = AccountsGetRequest(access_token=access_token)
        try:
            response = await asyncio.to_thread(self._client.accounts_get, request)
        except ApiException as exc:
            raise ProviderError(_sanitize_error(exc)) from exc

        accounts: list[RawPlaidAccount] = []
        for a in response.accounts:
            balances = a.balances
            accounts.append(
                RawPlaidAccount(
                    external_account_id=a.account_id,
                    name=a.name,
                    official_name=a.official_name,
                    plaid_type=str(a.type),
                    plaid_subtype=str(a.subtype) if a.subtype else None,
                    mask=a.mask,
                    currency=balances.iso_currency_code or "USD",
                    current_balance=Decimal(str(balances.current)) if balances.current is not None else None,
                    available_balance=Decimal(str(balances.available)) if balances.available is not None else None,
                )
            )
        return accounts

    async def sync_transactions(self, access_token: str, cursor: str | None) -> TransactionsSyncResult:
        """Read every page of a Plaid transaction patch set before the
        caller persists the cursor. Persisting a partial cursor would lose
        changes when Plaid returns multiple pages.
        """
        current_cursor = cursor
        added_or_modified: list[RawPlaidTransaction] = []
        removed_external_transaction_ids: list[str] = []
        while True:
            # The Plaid SDK validates optional fields at construction time.
            # Omit cursor entirely for an initial sync; passing None raises a
            # local ApiTypeError before any request reaches Plaid.
            if current_cursor is None:
                request = TransactionsSyncRequest(access_token=access_token, count=500)
            else:
                request = TransactionsSyncRequest(
                    access_token=access_token,
                    cursor=current_cursor,
                    count=500,
                )
            try:
                response = await asyncio.to_thread(self._client.transactions_sync, request)
            except ApiException as exc:
                raise ProviderError(_sanitize_error(exc)) from exc

            added_or_modified.extend(_to_raw_transaction(transaction) for transaction in response.added)
            added_or_modified.extend(_to_raw_transaction(transaction) for transaction in response.modified)
            removed_external_transaction_ids.extend(transaction.transaction_id for transaction in response.removed)
            current_cursor = response.next_cursor
            if not response.has_more:
                return TransactionsSyncResult(
                    added_or_modified=added_or_modified,
                    removed_external_transaction_ids=removed_external_transaction_ids,
                    next_cursor=current_cursor,
                )

    async def get_holdings(self, access_token: str) -> tuple[list[str], list[RawPlaidHolding]]:
        request = InvestmentsHoldingsGetRequest(access_token=access_token)
        try:
            response = await asyncio.to_thread(self._client.investments_holdings_get, request)
        except ApiException as exc:
            raise ProviderError(_sanitize_error(exc)) from exc

        securities = {security.security_id: security for security in response.securities}
        as_of = date.today()
        holdings: list[RawPlaidHolding] = []
        for holding in response.holdings:
            security = securities.get(holding.security_id)
            symbol = (security.ticker_symbol if security else None) or (security.name if security else None) or "UNKNOWN"
            holdings.append(
                RawPlaidHolding(
                    external_account_id=holding.account_id,
                    symbol=symbol[:20],
                    quantity=Decimal(str(holding.quantity)),
                    cost_basis=Decimal(str(holding.cost_basis or 0)),
                    market_value=Decimal(str(holding.institution_value)),
                    security_type=str(security.type) if security and security.type else None,
                    is_cash_equivalent=bool(security and security.is_cash_equivalent),
                    as_of=holding.institution_price_as_of or as_of,
                )
            )
        return [account.account_id for account in response.accounts], holdings


def _to_raw_transaction(transaction) -> RawPlaidTransaction:
    category = transaction.personal_finance_category.primary if transaction.personal_finance_category else None
    return RawPlaidTransaction(
        external_transaction_id=transaction.transaction_id,
        external_account_id=transaction.account_id,
        posted_at=transaction.date,
        merchant=transaction.merchant_name or transaction.name,
        category=category or "Uncategorized",
        # Plaid uses the inverse cash-flow sign from the app's normalized
        # convention: positive is money out, negative is money in.
        amount=-Decimal(str(transaction.amount)),
        pending=transaction.pending,
    )
