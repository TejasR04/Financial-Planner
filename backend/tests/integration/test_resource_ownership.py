from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.persistence.models import RecommendationModel

from .conftest import register_and_authorize


async def _create_scenario(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    response = await client.post(
        "/api/v1/scenarios",
        headers=headers,
        json={
            "name": name,
            "current_age": 35,
            "retirement_age": 65,
            "monthly_contribution": "1000",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.asyncio
async def test_scenario_operations_are_scoped_to_the_authenticated_user(
    client: AsyncClient,
) -> None:
    owner_headers = await register_and_authorize(client, "scenario-owner@example.com")
    other_headers = await register_and_authorize(client, "scenario-other@example.com")
    owner_scenario_id = await _create_scenario(client, owner_headers, "Owner plan")
    other_scenario_id = await _create_scenario(client, other_headers, "Other plan")

    run_body = {
        "current_age": 35,
        "current_retirement_balance": "50000",
        "include_monte_carlo": False,
    }
    owner_run = await client.post(
        f"/api/v1/scenarios/{owner_scenario_id}/run",
        headers=owner_headers,
        json=run_body,
    )
    assert owner_run.status_code == 201, owner_run.text

    attempts = [
        ("GET", f"/api/v1/scenarios/{owner_scenario_id}", None),
        ("PATCH", f"/api/v1/scenarios/{owner_scenario_id}", {"name": "Stolen"}),
        ("DELETE", f"/api/v1/scenarios/{owner_scenario_id}", None),
        ("POST", f"/api/v1/scenarios/{owner_scenario_id}/duplicate", None),
        ("POST", f"/api/v1/scenarios/{owner_scenario_id}/run", run_body),
        ("POST", f"/api/v1/scenarios/{owner_scenario_id}/preview", run_body),
        ("GET", f"/api/v1/scenarios/{owner_scenario_id}/runs", None),
        (
            "POST",
            f"/api/v1/scenarios/{owner_scenario_id}/sensitivity",
            {"current_age": 35, "current_retirement_balance": "50000"},
        ),
    ]
    for method, path, body in attempts:
        response = await client.request(method, path, headers=other_headers, json=body)
        assert response.status_code == 404, (method, path, response.text)

    compare = await client.post(
        "/api/v1/scenarios/compare",
        headers=other_headers,
        json={"scenario_ids": [other_scenario_id, owner_scenario_id]},
    )
    assert compare.status_code == 404, compare.text

    owner_after = await client.get(
        f"/api/v1/scenarios/{owner_scenario_id}", headers=owner_headers
    )
    assert owner_after.status_code == 200
    assert owner_after.json()["name"] == "Owner plan"

    other_list = await client.get("/api/v1/scenarios", headers=other_headers)
    assert other_list.status_code == 200
    assert [row["id"] for row in other_list.json()] == [other_scenario_id]


@pytest.mark.asyncio
async def test_recommendation_status_is_scoped_to_the_authenticated_user(
    client: AsyncClient,
    test_engine,
) -> None:
    owner_headers = await register_and_authorize(client, "recommendation-owner@example.com")
    other_headers = await register_and_authorize(client, "recommendation-other@example.com")
    owner = await client.get("/api/v1/users/me", headers=owner_headers)
    assert owner.status_code == 200

    recommendation_id = uuid4()
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add(
            RecommendationModel(
                id=recommendation_id,
                user_id=UUID(owner.json()["id"]),
                title="Owner-only recommendation",
                body="Sensitive planning recommendation",
                category="Security test",
                impact_value=Decimal("100.00"),
                effort="low",
                confidence=0.8,
                status="new",
            )
        )
        await session.commit()

    denied = await client.patch(
        f"/api/v1/recommendations/{recommendation_id}",
        headers=other_headers,
        json={"status": "dismissed"},
    )
    assert denied.status_code == 404, denied.text

    owner_rows = await client.get("/api/v1/recommendations?status=new", headers=owner_headers)
    assert owner_rows.status_code == 200
    assert [row["id"] for row in owner_rows.json()] == [str(recommendation_id)]


@pytest.mark.asyncio
async def test_transaction_category_update_is_scoped_to_the_authenticated_user(
    client: AsyncClient,
) -> None:
    owner_headers = await register_and_authorize(client, "transaction-owner@example.com")
    other_headers = await register_and_authorize(client, "transaction-other@example.com")

    account = await client.post(
        "/api/v1/accounts",
        headers=owner_headers,
        json={"name": "Owner checking", "type": "depository", "balance": "1000"},
    )
    assert account.status_code == 201
    transaction = await client.post(
        "/api/v1/transactions",
        headers=owner_headers,
        json={
            "account_id": account.json()["id"],
            "posted_at": date.today().isoformat(),
            "merchant": "Private merchant",
            "category": "original",
            "amount": "-25.00",
            "type": "expense",
        },
    )
    assert transaction.status_code == 201

    denied = await client.patch(
        f"/api/v1/transactions/{transaction.json()['id']}",
        headers=other_headers,
        json={"category": "tampered"},
    )
    assert denied.status_code == 404, denied.text

    owner_rows = await client.get("/api/v1/transactions", headers=owner_headers)
    assert owner_rows.status_code == 200
    assert owner_rows.json()["data"][0]["category"] == "original"
