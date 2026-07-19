"""PlaidProvider — implements FinancialDataProvider using Plaid as the
upstream source, plus the extra link-flow methods (`create_link_token`,
`link_new_institution`) that don't fit that interface since they're
onboarding operations, not periodic data reads.

Phase A (current state): link-token creation, public-token exchange, and
initial account balances. `get_transactions`/`get_holdings` are still
stubs — Phase B/C in ARCHITECTURE.md.

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
from app.domain.enums import AccountStatus, AccountType
from app.persistence.repositories.institution_repository import InstitutionRepository
from app.providers.base import FinancialDataProvider
from app.providers.plaid_client import PlaidClient, RawPlaidAccount

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

    # -- Link flow (Phase A) --------------------------------------------

    async def create_link_token(self, user_id: UUID) -> LinkTokenResult:
        result = await self._client.create_link_token(user_id)
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

    # -- FinancialDataProvider interface (Phase B/C wire the rest) -------

    async def get_accounts(self, user_id: UUID) -> list[Account]:
        raise ProviderError("Bulk re-sync not yet implemented (see ARCHITECTURE.md Phase 6 follow-up)")

    async def get_transactions(self, user_id: UUID, since: date) -> list[Transaction]:
        raise ProviderError("PlaidProvider transactions sync is not yet implemented (Phase B)")

    async def get_holdings(self, user_id: UUID, account_id: UUID) -> list[Holding]:
        raise ProviderError("PlaidProvider holdings sync is not yet implemented (Phase C)")


def _to_account_entity(user_id: UUID, institution_id: UUID, raw: RawPlaidAccount) -> Account:
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
