from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services import agent_token_service


def test_generated_agent_token_is_opaque_and_hashes_to_fixed_sha256() -> None:
    token = agent_token_service.generate_agent_token()

    assert token.startswith("mrd_")
    assert len(token) >= 40
    assert agent_token_service.visible_token_prefix(token) == token[:12]
    assert len(agent_token_service.hash_agent_token(token)) == 64
    assert token != agent_token_service.generate_agent_token()


def test_agent_token_expires_after_one_year() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert agent_token_service.token_expiry(now) == now + timedelta(days=365)


@pytest.mark.asyncio
async def test_reporting_auth_hashes_the_presented_secret_and_returns_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    token_id = uuid4()
    token = "mrd_" + "x" * 43
    repo = SimpleNamespace(
        get_active_for_hash=AsyncMock(
            return_value=SimpleNamespace(
                id=token_id,
                user_id=user_id,
                scopes=["reports:read"],
            )
        )
    )
    monkeypatch.setattr(agent_token_service, "AgentTokenRepository", lambda _session: repo)

    principal = await agent_token_service.authenticate_reporting_token(AsyncMock(), token)

    assert principal is not None
    assert principal.user_id == user_id
    assert principal.token_id == token_id
    assert principal.scopes == frozenset({"reports:read"})
    repo.get_active_for_hash.assert_awaited_once_with(agent_token_service.hash_agent_token(token))


@pytest.mark.asyncio
@pytest.mark.parametrize("scopes", [[], ["transactions:read"], None])
async def test_reporting_auth_rejects_token_without_reports_scope(
    monkeypatch: pytest.MonkeyPatch, scopes: list[str] | None
) -> None:
    row = SimpleNamespace(id=uuid4(), user_id=uuid4(), scopes=scopes)
    repo = SimpleNamespace(get_active_for_hash=AsyncMock(return_value=row))
    monkeypatch.setattr(agent_token_service, "AgentTokenRepository", lambda _session: repo)

    principal = await agent_token_service.authenticate_reporting_token(AsyncMock(), "mrd_" + "x" * 43)

    assert principal is None


@pytest.mark.asyncio
async def test_reporting_auth_rejects_expired_revoked_or_archived_token(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = SimpleNamespace(get_active_for_hash=AsyncMock(return_value=None))
    monkeypatch.setattr(agent_token_service, "AgentTokenRepository", lambda _session: repo)

    principal = await agent_token_service.authenticate_reporting_token(AsyncMock(), "mrd_" + "x" * 43)

    assert principal is None
