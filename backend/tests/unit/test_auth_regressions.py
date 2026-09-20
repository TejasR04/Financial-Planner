from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, Response
from passlib.hash import bcrypt

from app.api.deps import get_db
from app.api.v1.routes import auth
from app.core.config import get_settings
from app.core.security import hash_password, verify_password, verify_password_and_update
from app.schemas.auth import TokenResponse


@pytest.mark.parametrize("prefix", ["x" * 72, "猫" * 30])
def test_new_password_hash_checks_bytes_beyond_bcrypt_limit(prefix: str) -> None:
    hashed = hash_password(prefix + "A")
    assert verify_password(prefix + "A", hashed)
    assert not verify_password(prefix + "B", hashed)
    assert not verify_password(prefix, hashed)


def test_legacy_bcrypt_verifies_and_upgrades_without_resetting_password() -> None:
    password = "existing account password"
    legacy = bcrypt.hash(password)
    valid, upgraded = verify_password_and_update(password, legacy)
    assert valid and upgraded is not None
    assert verify_password(password, upgraded)
    assert verify_password_and_update(password, upgraded) == (True, None)
    assert verify_password_and_update("wrong password", legacy) == (False, None)


def test_password_at_accepted_unicode_length_is_not_truncated() -> None:
    password = "猫" * 128
    hashed = hash_password(password)
    assert verify_password(password, hashed)
    assert not verify_password(password[:-1] + "犬", hashed)


def auth_test_app(db: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")

    async def fake_db():
        yield db

    app.dependency_overrides[get_db] = fake_db
    return app


@pytest.mark.asyncio
async def test_registration_is_rejected_when_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    db = AsyncMock()
    repo = AsyncMock()
    monkeypatch.setattr(auth, "get_settings", lambda: SimpleNamespace(registration_enabled=False))
    monkeypatch.setattr(auth, "UserRepository", lambda session: repo)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=auth_test_app(db)), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "not-allowed", "full_name": "New User"},
        )
    assert response.status_code == 403
    assert response.json() == {"detail": "Registration is closed"}
    repo.get_by_email.assert_not_awaited()


def test_cookie_deletion_preserves_cross_site_cookie_attributes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "get_settings", lambda: SimpleNamespace(
        refresh_cookie_name="meridian_refresh", api_v1_prefix="/api/v1",
        refresh_cookie_secure=True, refresh_cookie_samesite="none",
    ))
    response = Response()
    auth._clear_refresh_cookie(response)
    cookie = response.headers["set-cookie"]
    assert "SameSite=none" in cookie and "Secure" in cookie and "HttpOnly" in cookie
    assert "Max-Age=0" in cookie and "Path=/api/v1/auth" in cookie


@pytest.mark.asyncio
async def test_invalid_refresh_cookie_is_deleted_on_the_error_response(monkeypatch: pytest.MonkeyPatch) -> None:
    db = AsyncMock()
    repo = AsyncMock()
    repo.consume.return_value = None
    monkeypatch.setattr(auth, "RefreshSessionRepository", lambda session: repo)
    cookie_name = get_settings().refresh_cookie_name
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=auth_test_app(db)), base_url="http://test"
    ) as client:
        client.cookies.set(cookie_name, "expired-audit-token", domain="test.local", path="/api/v1/auth")
        response = await client.post("/api/v1/auth/refresh")
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid refresh token"}
        assert "Max-Age=0" in response.headers["set-cookie"]
        assert "Path=/api/v1/auth" in response.headers["set-cookie"]
        assert client.cookies.get(cookie_name) is None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_login_persists_legacy_hash_upgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    db = AsyncMock()
    repo = AsyncMock()
    user_id = uuid4()
    password = "an existing long password " * 4
    repo.get_hashed_password.return_value = (SimpleNamespace(id=user_id), bcrypt.hash(password))
    monkeypatch.setattr(auth, "UserRepository", lambda session: repo)
    monkeypatch.setattr(auth, "_start_session", AsyncMock(return_value=TokenResponse(access_token="test-access")))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=auth_test_app(db)), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/auth/login", json={"email": "legacy@example.com", "password": password})
    assert response.status_code == 200
    repo.update_password.assert_awaited_once()
    updated_user, updated_hash = repo.update_password.await_args.args
    assert updated_user == user_id
    assert verify_password(password, updated_hash)
    assert not verify_password(password + "typo", updated_hash)
    db.commit.assert_awaited_once()
