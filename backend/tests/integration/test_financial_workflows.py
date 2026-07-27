from datetime import date

import pytest
from httpx import AsyncClient

from .conftest import register_and_authorize


@pytest.mark.asyncio
async def test_authenticated_user_can_create_and_filter_transactions(client: AsyncClient) -> None:
    headers = await register_and_authorize(client)
    account_response = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Everyday Checking", "type": "depository", "balance": "2450.00"},
    )
    assert account_response.status_code == 201, account_response.text
    account_id = account_response.json()["id"]

    transaction_response = await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": account_id,
            "posted_at": date.today().isoformat(),
            "merchant": "Corner Market",
            "category": "rent_and_utilities",
            "amount": "-125.45",
            "type": "expense",
        },
    )
    assert transaction_response.status_code == 201, transaction_response.text

    filtered = await client.get("/api/v1/transactions?category=REN", headers=headers)
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["data"][0]["merchant"] == "Corner Market"

    other_headers = await register_and_authorize(client, "other@example.com")
    inaccessible = await client.get(f"/api/v1/accounts/{account_id}", headers=other_headers)
    assert inaccessible.status_code == 404


@pytest.mark.asyncio
async def test_budget_assignment_is_reflected_in_monthly_summary(client: AsyncClient) -> None:
    headers = await register_and_authorize(client)
    categories = await client.get("/api/v1/budgets/categories", headers=headers)
    assert categories.status_code == 200
    groceries = next(category for category in categories.json() if category["name"] == "Groceries")

    updated_category = await client.patch(
        f"/api/v1/budgets/categories/{groceries['id']}",
        headers=headers,
        json={"monthly_limit": "300.00"},
    )
    assert updated_category.status_code == 200

    account = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Cash", "type": "depository", "balance": "500.00"},
    )
    transaction = await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": account.json()["id"],
            "posted_at": date.today().isoformat(),
            "merchant": "Neighborhood Grocer",
            "category": "food_and_drink",
            "amount": "-87.50",
            "type": "expense",
        },
    )
    assert transaction.status_code == 201

    assignment = await client.patch(
        f"/api/v1/transactions/{transaction.json()['id']}/budget-category",
        headers=headers,
        json={"budget_category_id": groceries["id"]},
    )
    assert assignment.status_code == 200

    summary = await client.get(f"/api/v1/budgets/summary?month={date.today().replace(day=1).isoformat()}", headers=headers)
    assert summary.status_code == 200
    grocery_summary = next(category for category in summary.json()["categories"] if category["name"] == "Groceries")
    assert grocery_summary["budgeted"] == "300.00"
    assert grocery_summary["spent"] == "87.50"
    assert summary.json()["uncategorized"]["transaction_count"] == 0


@pytest.mark.asyncio
async def test_agent_reports_missing_gemini_configuration(client: AsyncClient) -> None:
    headers = await register_and_authorize(client, "ai-config@example.com")
    response = await client.post("/api/v1/agent/chat", headers=headers, json={"message": "Summarize my plan"})

    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]

    history = await client.get("/api/v1/agent/history", headers=headers)
    assert history.status_code == 200
    assert history.json() == []

    cleared = await client.delete("/api/v1/agent/history", headers=headers)
    assert cleared.status_code == 204


@pytest.mark.asyncio
async def test_rule_based_insight_refresh_replaces_previous_results(client: AsyncClient) -> None:
    headers = await register_and_authorize(client, "insight-refresh@example.com")
    account = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Emergency Fund", "type": "depository", "balance": "5000.00"},
    )
    assert account.status_code == 201

    health = await client.post("/api/v1/financial-health/recalculate", headers=headers, json={})
    assert health.status_code == 200, health.text

    first = await client.post("/api/v1/insights/generate", headers=headers)
    second = await client.post("/api/v1/insights/generate", headers=headers)
    listed = await client.get("/api/v1/insights", headers=headers)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert listed.status_code == 200
    assert len(listed.json()) == len(second.json())
    assert {row["text"] for row in listed.json()} == {row["text"] for row in second.json()}
    assert {row["id"] for row in listed.json()}.isdisjoint(
        {row["id"] for row in first.json()}
    )
