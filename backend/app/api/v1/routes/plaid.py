"""Plaid Link flow endpoints (Phase A).

Both routes require an authenticated user via `get_current_user` — there
is no path here that accepts a client-supplied user id. `client_id` and
`secret` are read once from Settings (server-side env vars only) and
never appear in any response; Plaid API errors are sanitized by
`PlaidClient` before they ever reach here.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.domain.entities import User
from app.persistence.repositories.account_repository import AccountRepository
from app.providers.plaid_provider import PlaidProvider
from app.schemas.account import AccountResponse
from app.schemas.plaid import (
    PlaidExchangePublicTokenRequest,
    PlaidExchangePublicTokenResponse,
    PlaidInstitutionResponse,
    PlaidLinkTokenRequest,
    PlaidLinkTokenResponse,
    PlaidRefreshInstitutionResponse,
    PlaidRefreshResponse,
)

router = APIRouter(prefix="/plaid", tags=["plaid"])


def _get_provider(db: AsyncSession) -> PlaidProvider:
    settings = get_settings()
    return PlaidProvider(db, settings.plaid_client_id, settings.plaid_secret, settings.plaid_env)


@router.post("/link-token", response_model=PlaidLinkTokenResponse)
async def create_link_token(
    body: PlaidLinkTokenRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlaidLinkTokenResponse:
    provider = _get_provider(db)
    result = await provider.create_link_token(
        current_user.id,
        institution_id=body.institution_id if body else None,
    )
    return PlaidLinkTokenResponse(link_token=result.link_token, expiration=result.expiration)


@router.post("/exchange-public-token", response_model=PlaidExchangePublicTokenResponse)
async def exchange_public_token(
    body: PlaidExchangePublicTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlaidExchangePublicTokenResponse:
    provider = _get_provider(db)
    result = await provider.link_new_institution(current_user.id, body.public_token)

    account_repo = AccountRepository(db)
    saved_accounts = [
        await account_repo.upsert_from_plaid(current_user.id, account) for account in result.accounts
    ]
    await db.commit()

    # A U.S. institution may take a moment to make Transactions available
    # after Link. Keep the successful account link, but immediately attempt
    # the first complete sync and retain any actionable sync error.
    try:
        await provider.refresh_institution(current_user.id, result.institution.id)
    except ProviderError:
        pass
    await db.commit()

    return PlaidExchangePublicTokenResponse(
        institution=PlaidInstitutionResponse.model_validate(result.institution, from_attributes=True),
        accounts=[AccountResponse.model_validate(a, from_attributes=True) for a in saved_accounts],
    )


@router.post("/refresh", response_model=PlaidRefreshResponse)
async def refresh_plaid_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlaidRefreshResponse:
    """Synchronize all of the current user's linked Plaid Items.

    A failure in one institution does not discard successful updates from
    another. The per-institution result lets the frontend surface an
    actionable reconnect/error state without guessing which Item failed.
    """
    provider = _get_provider(db)
    results = await provider.refresh(current_user.id)
    await db.commit()
    return PlaidRefreshResponse(
        data=[
            PlaidRefreshInstitutionResponse(
                institution_id=result.institution_id,
                institution_name=result.institution_name,
                status=result.status,
                accounts_synced=result.accounts_synced,
                transactions_created=result.transactions_created,
                transactions_updated=result.transactions_updated,
                transactions_removed=result.transactions_removed,
                holdings_synced=result.holdings_synced,
                error=result.error,
            )
            for result in results
        ]
    )
