import pytest
from httpx import AsyncClient

from app.api.v1.routes import auth as auth_routes


REGISTER_BODY = {
    "email": "session-test@example.com",
    "password": "correct-horse-battery-staple",
    "full_name": "Session Test",
}


@pytest.mark.asyncio
async def test_refresh_cookie_rotates_and_logout_revokes_session(client: AsyncClient) -> None:
    registered = await client.post("/api/v1/auth/register", json=REGISTER_BODY)
    assert registered.status_code == 201, registered.text
    assert "refresh_token" not in registered.json()
    assert "HttpOnly" in registered.headers["set-cookie"]

    original_refresh = client.cookies["meridian_refresh"]
    refreshed = await client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    rotated_refresh = client.cookies["meridian_refresh"]
    assert rotated_refresh != original_refresh

    logged_out = await client.post("/api/v1/auth/logout")
    assert logged_out.status_code == 204
    assert client.cookies.get("meridian_refresh") is None

    denied = await client.post("/api/v1/auth/refresh")
    assert denied.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_reuse_revokes_the_rotated_session(client: AsyncClient) -> None:
    registered = await client.post(
        "/api/v1/auth/register",
        json={**REGISTER_BODY, "email": "reuse-test@example.com"},
    )
    assert registered.status_code == 201
    original_refresh = client.cookies["meridian_refresh"]

    rotated = await client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    rotated_refresh = client.cookies["meridian_refresh"]

    client.cookies.set("meridian_refresh", original_refresh, path="/api/v1/auth")
    reuse = await client.post("/api/v1/auth/refresh")
    assert reuse.status_code == 401

    client.cookies.set("meridian_refresh", rotated_refresh, path="/api/v1/auth")
    revoked_replacement = await client.post("/api/v1/auth/refresh")
    assert revoked_replacement.status_code == 401


@pytest.mark.asyncio
async def test_password_reset_token_is_single_use(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = "password-reset@example.com"
    registered = await client.post(
        "/api/v1/auth/register",
        json={**REGISTER_BODY, "email": email},
    )
    assert registered.status_code == 201

    delivered: list[str] = []
    monkeypatch.setattr(
        auth_routes,
        "send_password_reset_email",
        lambda recipient, token: delivered.append(token),
    )
    requested = await client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": email},
    )
    assert requested.status_code == 202
    assert len(delivered) == 1

    reset = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": delivered[0], "password": "new-correct-horse-password"},
    )
    assert reset.status_code == 204

    replay = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": delivered[0], "password": "attacker-chosen-password"},
    )
    assert replay.status_code == 400

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": REGISTER_BODY["password"]},
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "new-correct-horse-password"},
    )
    assert new_login.status_code == 200
