from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.agent_token_service import ReportingPrincipal, authenticate_reporting_token

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class ReportingUser:
    id: UUID
    token_id: UUID
    scopes: frozenset[str]


async def authenticate_bearer_for_reporting(session: AsyncSession, authorization: str | None) -> ReportingUser | None:
    if not authorization:
        return None
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        return None
    principal: ReportingPrincipal | None = await authenticate_reporting_token(session, token.strip())
    if principal is None:
        return None
    return ReportingUser(id=principal.user_id, token_id=principal.token_id, scopes=principal.scopes)


async def get_reporting_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> ReportingUser:
    authorization = f"Bearer {credentials.credentials}" if credentials is not None else None
    principal = await authenticate_bearer_for_reporting(db, authorization)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


async def get_reporting_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """Resolve the owner ID for REST reporting endpoints from an agent token."""
    authorization = f"Bearer {credentials.credentials}" if credentials is not None else None
    principal = await authenticate_bearer_for_reporting(db, authorization)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal.id


async def get_reporting_user_from_request(request: Request, db: AsyncSession) -> ReportingUser | None:
    """Shared MCP/REST verifier. Caller owns the session lifetime."""
    return await authenticate_bearer_for_reporting(db, request.headers.get("authorization"))
