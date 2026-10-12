from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.domain.entities import User
from app.persistence.repositories.agent_token_repository import AgentTokenRepository
from app.schemas.agent_token import (
    AgentTokenCreateRequest,
    AgentTokenCreatedResponse,
    AgentTokenListResponse,
    AgentTokenResponse,
)
from app.services.agent_token_service import (
    REPORTS_READ_SCOPE,
    generate_agent_token,
    hash_agent_token,
    token_expiry,
    visible_token_prefix,
)
from app.services.daily_reports import enable_reporting

router = APIRouter(prefix="/integrations/tokens", tags=["integrations"])


@router.post("", response_model=AgentTokenCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_token(
    body: AgentTokenCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentTokenCreatedResponse:
    if get_settings().environment.lower() == "demo":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent tokens are unavailable in demo mode")

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Token name is required")

    token = generate_agent_token()
    created_at = datetime.now(timezone.utc)
    expires_at = token_expiry(created_at)
    row = await AgentTokenRepository(db).create(
        user_id=current_user.id,
        name=name,
        token_hash=hash_agent_token(token),
        token_prefix=visible_token_prefix(token),
        expires_at=expires_at,
    )

    # Enabling reporting and issuing its first credential form one transaction.
    await enable_reporting(db, current_user.id)
    await db.commit()

    return AgentTokenCreatedResponse(
        id=row.id,
        name=row.name,
        token=token,
        prefix=row.token_prefix,
        created_at=row.created_at,
        expires_at=row.expires_at,
        scope=REPORTS_READ_SCOPE,
    )


@router.get("", response_model=AgentTokenListResponse)
async def list_agent_tokens(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentTokenListResponse:
    rows = await AgentTokenRepository(db).list_for_user(current_user.id)
    return AgentTokenListResponse(
        data=[
            AgentTokenResponse(
                id=row.id,
                name=row.name,
                prefix=row.token_prefix,
                created_at=row.created_at,
                expires_at=row.expires_at,
                revoked_at=row.revoked_at,
                scope=REPORTS_READ_SCOPE,
            )
            for row in rows
        ]
    )


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_agent_token(
    token_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    row = await AgentTokenRepository(db).revoke_for_user(current_user.id, token_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent token not found")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
