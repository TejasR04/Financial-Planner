from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.repositories.agent_token_repository import AgentTokenRepository

REPORTS_READ_SCOPE = "reports:read"
AGENT_TOKEN_PREFIX = "mrd_"
AGENT_TOKEN_TTL = timedelta(days=365)


@dataclass(frozen=True, slots=True)
class ReportingPrincipal:
    user_id: UUID
    token_id: UUID
    scopes: frozenset[str]


def generate_agent_token() -> str:
    """Create a 256-bit opaque token suitable for a single display to the user."""
    return AGENT_TOKEN_PREFIX + token_urlsafe(32)


def hash_agent_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def visible_token_prefix(token: str) -> str:
    return token[:12]


def token_expiry(now: datetime | None = None) -> datetime:
    base = now or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base + AGENT_TOKEN_TTL


async def authenticate_reporting_token(
    session: AsyncSession, token: str
) -> ReportingPrincipal | None:
    # The format check rejects obvious non-agent credentials without querying
    # the token table; the database hash remains the actual authentication.
    if not token.startswith(AGENT_TOKEN_PREFIX) or len(token) < 40:
        return None
    row = await AgentTokenRepository(session).get_active_for_hash(hash_agent_token(token))
    if row is None:
        return None
    scopes = row.scopes if isinstance(row.scopes, list) else []
    if REPORTS_READ_SCOPE not in scopes:
        return None
    return ReportingPrincipal(
        user_id=row.user_id,
        token_id=row.id,
        scopes=frozenset(scope for scope in scopes if isinstance(scope, str)),
    )
