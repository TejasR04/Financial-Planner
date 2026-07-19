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
from app.domain.entities import User
from app.persistence.repositories.account_repository import AccountRepository
from app.providers.plaid_provider import PlaidProvider
from app.schemas.account import AccountResponse
from app.schemas.plaid import (
    PlaidExchangePublicTokenRequest,
    PlaidExchangePublicTokenResponse,
    PlaidInstitutionResponse,
    PlaidLinkTokenResponse,
)

router = APIRouter(prefix="/plaid", tags=["plaid"])


def _get_provider(db: AsyncSession) -> PlaidProvider:
    settings = get_settings()
    return PlaidProvider(db, settings.plaid_client_id, settings.plaid_secret, settings.plaid_env)


@router.post("/link-token", response_model=PlaidLinkTokenResponse)
async def create_link_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlaidLinkTokenResponse:
    provider = _get_provider(db)
    result = await provider.create_link_token(current_user.id)
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

    return PlaidExchangePublicTokenResponse(
        institution=PlaidInstitutionResponse.model_validate(result.institution, from_attributes=True),
        accounts=[AccountResponse.model_validate(a, from_attributes=True) for a in saved_accounts],
    )
