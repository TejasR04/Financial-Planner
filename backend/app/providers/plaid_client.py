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
from datetime import datetime
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

    async def create_link_token(self, user_id: UUID) -> LinkTokenResult:
        request = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
            client_name="Meridian",
            products=[Products("transactions")],
            country_codes=[CountryCode("US")],
            language="en",
        )
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
