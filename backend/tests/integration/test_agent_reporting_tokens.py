from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from tests.integration.conftest import register_and_authorize


@pytest.mark.asyncio
async def test_agent_token_can_read_reports_but_not_financial_or_token_management_routes(
    client: AsyncClient,
) -> None:
    user_headers = await register_and_authorize(client, "report-agent@example.com")
    created = await client.post(
        "/api/v1/integrations/tokens",
        json={"name": "Hermes daily digest"},
        headers=user_headers,
    )
    assert created.status_code == 201, created.text
    created_json = created.json()
    assert created_json["scope"] == "reports:read"
    assert created_json["token"].startswith("mrd_")
    agent_headers = {"Authorization": f"Bearer {created_json['token']}"}

    summary = await client.get("/api/v1/reports/current", headers=agent_headers)
    assert summary.status_code == 200, summary.text

    assert (await client.get("/api/v1/budgets/summary", headers=agent_headers)).status_code == 401
    assert (await client.post(
        "/api/v1/accounts", json={"name": "Forbidden", "type": "depository", "balance": "1.00"},
        headers=agent_headers,
    )).status_code == 401
    assert (await client.get("/api/v1/integrations/tokens", headers=agent_headers)).status_code == 401
    assert (await client.get("/api/v1/reports/current")).status_code == 401

    listed = await client.get("/api/v1/integrations/tokens", headers=user_headers)
    assert listed.status_code == 200
    token_summary = listed.json()["data"][0]
    assert token_summary["id"] == created_json["id"]
    assert "token" not in token_summary
    assert "token_hash" not in token_summary

    revoked = await client.delete(
        f"/api/v1/integrations/tokens/{created_json['id']}", headers=user_headers
    )
    assert revoked.status_code == 204
    denied = await client.get("/api/v1/reports/current", headers=agent_headers)
    assert denied.status_code == 401


@pytest.mark.asyncio
async def test_other_user_cannot_revoke_agent_token(client: AsyncClient) -> None:
    owner_headers = await register_and_authorize(client, "report-token-owner@example.com")
    other_headers = await register_and_authorize(client, "report-token-other@example.com")
    created = await client.post(
        "/api/v1/integrations/tokens", json={"name": "Owner token"}, headers=owner_headers
    )
    assert created.status_code == 201, created.text

    response = await client.delete(
        f"/api/v1/integrations/tokens/{created.json()['id']}", headers=other_headers
    )

    assert response.status_code == 404
    assert (await client.get(
        "/api/v1/reports/current",
        headers={"Authorization": f"Bearer {created.json()['token']}"},
    )).status_code == 200


@pytest.mark.asyncio
async def test_demo_mode_does_not_issue_agent_tokens(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    user_headers = await register_and_authorize(client, "demo-agent@example.com")
    monkeypatch.setattr(get_settings(), "environment", "demo")

    response = await client.post(
        "/api/v1/integrations/tokens",
        json={"name": "Demo token"},
        headers=user_headers,
    )

    assert response.status_code == 403
    assert "token" not in response.json()
